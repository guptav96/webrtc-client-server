import argparse
import logging
import asyncio
import math
import ast
import cv2 as cv
import numpy as np
import fractions
import time
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
)
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
from av import VideoFrame

SCREEN_HEIGHT = 640
SCREEN_WIDTH = 480
VIDEO_CLOCK_RATE = 90000
VIDEO_PTIME = 1 / 30  # 30fps
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)

logger = logging.getLogger("server")


class BouncingBallTrack(MediaStreamTrack):
    """
    Represents a video track of a bouncing ball.
    """

    kind = "video"

    def __init__(self):
        super().__init__()

        self.screen_size = (SCREEN_HEIGHT, SCREEN_WIDTH)
        self.position_x = self.screen_size[0] // 2
        self.position_y = self.screen_size[1] // 2
        self.speed_x = 1
        self.speed_y = 1

        self.ball_radius = 20
        self.ball_color = (0, 0, 255)

    def update_delta_with_bound(self):
        """
        Update the ball's position and direction based on the screen boundaries.
        """
        if self.position_x + self.ball_radius >= self.screen_size[0]:
            self.speed_x *= -1
        elif self.position_x - self.ball_radius <= 0:
            self.speed_x *= -1
        if self.position_y + self.ball_radius >= self.screen_size[1]:
            self.speed_y *= -1
        elif self.position_y - self.ball_radius <= 0:
            self.speed_y *= -1

    def get_next_image(self):
        """
        Generate the next image with the bouncing ball.
        """
        frame = np.full((self.screen_size[1], self.screen_size[0], 3), 255, dtype="uint8")
        self.position_x += self.speed_x
        self.position_y += self.speed_y
        cv.circle(frame, (self.position_x, self.position_y), self.ball_radius, self.ball_color, -1)
        self.update_delta_with_bound()
        return frame

    async def next_timestamp(self):
        """
        Calculate the next timestamp for the video frame.
        """
        if hasattr(self, "_timestamp"):
            self._timestamp += int(VIDEO_PTIME * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            await asyncio.sleep(wait)
        else:
            self._start = time.time()
            self._timestamp = 0
        return self._timestamp, VIDEO_TIME_BASE

    async def recv(self):
        """
        Receive the next video frame.
        """
        next_img = self.get_next_image()
        next_frame = VideoFrame.from_ndarray(next_img, format="bgr24")

        pts, time_base = await self.next_timestamp()
        next_frame.pts = pts
        next_frame.time_base = time_base
        return next_frame


class Server:
    """
    Represents a server that generates a video stream of a bouncing ball and communicates with the client.
    """

    async def consume_signaling(self, peer_connection, signaling):
        """
        Consume signaling messages and handle them accordingly.
        """
        while True:
            obj = await signaling.receive()

            if isinstance(obj, RTCSessionDescription):
                await peer_connection.setRemoteDescription(obj)

                if obj.type == "offer":
                    # send answer
                    await peer_connection.setLocalDescription(await peer_connection.createAnswer())
                    await signaling.send(peer_connection.localDescription)
            elif isinstance(obj, RTCIceCandidate):
                await peer_connection.addIceCandidate(obj)
            elif obj is BYE:
                break
    
    def compute_error(self, balltrack, client_coordinate):
        """
        Calculates distance between the actual location of the ball and coordinates sent by the client.
        Args:
            balltrack: BouncingBallTrack instance.
            client_coordinate: Dictionary with x and y coordinates
        Returns:
            distance -> Float
        """
        actual_x = balltrack.position_x
        actual_y = balltrack.position_y
        distance = math.sqrt((client_coordinate["x"] - actual_x) ** 2 + (client_coordinate["y"] - actual_y) ** 2)
        logger.info(f"current coordinates > x: {actual_x}, y: {actual_y}. computed error: {distance} \n ------------------")
        return distance

    async def run_offer(self, peer_connection, signaling):
        """
        Run the server as an offerer, generating the video stream and communicating with the client.
        Args:
            peer_connection: The RTCPeerConnection instance.
            signaling: The signaling instance.
        """
        await signaling.connect()

        channel = peer_connection.createDataChannel("coordinates")
        logger.info(f"channel({channel.label}) - created by local party")

        # add tracks
        balltrack = BouncingBallTrack()
        peer_connection.addTrack(balltrack)

        @channel.on("message")
        def on_message(message):
            # message received from the client, compute error
            if isinstance(message, str):
                client_coordinate = ast.literal_eval(message)
                logger.info(f"channel({channel.label}) < {client_coordinate}")
                self.compute_error(balltrack, client_coordinate)                

        # create offer and send it to the client
        await peer_connection.setLocalDescription(await peer_connection.createOffer())
        await signaling.send(peer_connection.localDescription)
        await self.consume_signaling(peer_connection, signaling)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server Command Line Interface")
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

    server = Server()

    # create a new event loop and set it to current
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # future to send the images to the client and get back the computed coordinates
        loop.run_until_complete(server.run_offer(peer_connection, signaling))
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(peer_connection.close())
        loop.run_until_complete(signaling.close())
