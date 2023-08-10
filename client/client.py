import argparse
import logging
import asyncio
import queue
import multiprocessing as mp
import cv2 as cv
import numpy as np
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    MediaStreamTrack,
)
from aiortc.contrib.signaling import TcpSocketSignaling, BYE
from aiortc.contrib.media import MediaRelay

logger = logging.getLogger("client")


class VideoReceiveTrack(MediaStreamTrack):
    """
    Custom video receiver for receiving and displaying video frames.
    """

    kind = "video"

    def __init__(self, track, image_queue):
        """
        Initialize the video receive track.
        Args:
            track: The underlying media track.
            image_queue: A queue to store received image frames.
        """
        super().__init__()
        self.track = track
        self.image_queue = image_queue

    def process_image(self, image):
        """
        Process and display the image frame.
        Args:
            image: The image frame to be processed.
        """
        cv.imshow("Remote Stream", image)
        cv.waitKey(10)
        self.image_queue.put(image)

    async def recv(self):
        """
        Receive a video frame.
        Returns:
            The received video frame.
        """
        frame = await self.track.recv()
        image = frame.to_ndarray(format="bgr24")
        self.process_image(image)
        return frame


class ImageParser(mp.Process):
    """
    A multiprocessing process for parsing the image and computing the current location of the ball.
    """

    def __init__(self, image_queue, coordinate_queue):
        """
        Initialize the process.
        Args:
            image_queue: A queue for receiving image frames.
            coordinate_queue: A queue for storing coordinates of the ball.
        """
        super().__init__()
        self.image_queue = image_queue
        self.coordinate_queue = coordinate_queue
        self.current_x = mp.Value("i", 0)
        self.current_y = mp.Value("i", 0)

    def detect_center(self, image):
        """
        Detect the center of the ball in the image
        Args:
            image: The image (ndarray) object
        Returns:
            (x, y) -> Tuple representing the center of ball
        """
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        gray_blurred = cv.blur(gray, (3, 3))
        detected_circles = cv.HoughCircles(
            gray_blurred,
            cv.HOUGH_GRADIENT,
            1,
            20,
            param1=50,
            param2=30,
            minRadius=1,
            maxRadius=40,
        )

        if detected_circles is not None:
            x, y, _ = np.uint16(np.around(detected_circles))[0, :][0]
            return (x, y)

        return None

    def run(self):
        """
        Run the image parsing loop.
        """
        while True:
            try:
                image = self.image_queue.get()
            except queue.Empty:
                logger.debug("image queue is empty")

            # extracting the center of the bouncing ball
            center = self.detect_center(image)
            if center is not None:
                self.current_x.value = center[0]
                self.current_y.value = center[1]
                self.coordinate_queue.put(
                    {"x": self.current_x.value, "y": self.current_y.value}
                )


class Client:
    """
    The client class for video signaling.
    """

    def __init__(self):
        """
        Initialize the client with image queue, coordinate queue, and data channel.
        """
        self.image_queue = mp.Queue()
        self.coordinate_queue = mp.Queue()
        self.channel = None

    async def send_coordinates_to_server(self):
        """
        Send the computed coordinates to the server.
        """
        while True:
            if (
                self.channel
                and self.channel.readyState == "open"
                and not self.coordinate_queue.empty()
            ):
                coordinates = self.coordinate_queue.get()
                logger.info(f"channel({self.channel.label}) > {coordinates}")
                self.channel.send(str(coordinates))
            await asyncio.sleep(0.01)  # Adjust the sleep duration as needed

    async def consume_signaling(self, peer_connection, signaling) -> None:
        """
        Consume signaling messages from the server.
        Args:
            peer_connection: The RTCPeerConnection instance.
            signaling: The signaling instance.
        """
        while True:
            obj = await signaling.receive()

            if isinstance(obj, RTCSessionDescription):
                await peer_connection.setRemoteDescription(obj)

                if obj.type == "offer":
                    # send answer
                    await peer_connection.setLocalDescription(
                        await peer_connection.createAnswer()
                    )
                    await signaling.send(peer_connection.localDescription)
            elif isinstance(obj, RTCIceCandidate):
                await peer_connection.addIceCandidate(obj)
            elif obj is BYE:
                break

    async def run_answer(self, peer_connection, signaling) -> None:
        """
        Run the client's answer loop.
        Args:
            peer_connection: The RTCPeerConnection instance.
            signaling: The signaling instance.
        """
        await signaling.connect()

        def on_track(track):
            if track.kind == "video":
                relay = MediaRelay()
                video_track = VideoReceiveTrack(relay.subscribe(track), self.image_queue)
                peer_connection.addTrack(video_track)

        def on_datachannel(channel):
            self.channel = channel

        peer_connection.on("track")(on_track)
        peer_connection.on("datachannel")(on_datachannel)

        await self.consume_signaling(peer_connection, signaling)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client Command Line Interface")
    parser.add_argument("--signaling-host", default="127.0.0.1", help="signaling host")
    parser.add_argument("--signaling-port", default=8080, type=int, help="signaling port")
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # create signaling and peer connection
    signaling = TcpSocketSignaling(args.signaling_host, args.signaling_port)
    peer_connection = RTCPeerConnection()

    client = Client()

    # start process_a for parsing the image and detecting the center of the ball
    process_a = ImageParser(client.image_queue, client.coordinate_queue)
    process_a.start()

    # create a new event loop and set it to current
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # task to send the coordinates to the server on the main thread
        loop.create_task(client.send_coordinates_to_server())
        # future to fetch images from the server and display them
        loop.run_until_complete(client.run_answer(peer_connection, signaling))
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(peer_connection.close())
        loop.run_until_complete(signaling.close())
