import pytest
import cv2 as cv
from unittest.mock import MagicMock
from client import VideoReceiveTrack, Client, ImageParser
import numpy as np
import multiprocessing as mp

@pytest.fixture
def client():
    return Client()

def test_client_initialization(client):
    assert client.image_queue.empty()
    assert client.coordinate_queue.empty()
    assert client.channel is None

def test_process_image(mocker):
    # Mock the cv.imshow and cv.waitKey functions
    mocker.patch.object(cv, "imshow")
    mocker.patch.object(cv, "waitKey")

    # Create a VideoReceiveTrack instance
    image_queue = mp.Queue()
    track = mocker.Mock()
    video_track = VideoReceiveTrack(track, image_queue)

    # Mock an image frame
    image_frame = mocker.Mock()
    image_frame.to_ndarray.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    # Call the process_image function
    video_track.process_image(image_frame.to_ndarray())

    # Assert that cv.imshow and cv.waitKey were called with the correct arguments
    cv.imshow.assert_called_once_with("Remote Stream", image_frame.to_ndarray())
    cv.waitKey.assert_called_once_with(10)

    assert np.array_equal(image_queue.get(), image_frame.to_ndarray())

def test_detect_center():
    image_queue = mp.Queue()
    coordinate_queue = mp.Queue()
    image_parser = ImageParser(image_queue, coordinate_queue)
    image_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    center = image_parser.detect_center(image_frame)
    assert center is None

def test_send_coordinates_to_server(client):
    client.channel = MagicMock()
    client.channel.readyState = "open"
    client.coordinate_queue.put({"x": 10, "y": 20})
    client.send_coordinates_to_server()

    assert client.channel.send.called_with('{"x": 10, "y": 20}')

if __name__ == "__main__":
    pytest.main()
