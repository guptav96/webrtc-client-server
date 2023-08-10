import pytest
from av import VideoFrame
from server import BouncingBallTrack, Server
import numpy as np
import math

@pytest.mark.asyncio
async def test_BouncingBallTrack_recv():
    track = BouncingBallTrack()

    received_frame = await track.recv()
    assert received_frame is not None
    assert isinstance(received_frame.width, int)
    assert isinstance(received_frame.height, int)
    assert isinstance(received_frame, VideoFrame)

def test_BouncingBallTrack_get_next_image():
    track = BouncingBallTrack()

    received_frame = track.get_next_image()
    assert isinstance(received_frame, np.ndarray)

def test_Server_compute_error():
    server = Server()
    balltrack = BouncingBallTrack()

    # Test case 1: Client coordinate at (0, 0)
    client_coordinate = {"x": 0, "y": 0}
    distance = server.compute_error(balltrack, client_coordinate)
    assert distance == math.sqrt(balltrack.position_x ** 2 + balltrack.position_y ** 2)

    # Test case 2: Client coordinate at (10, 20)
    client_coordinate = {"x": 10, "y": 20}
    actual_x = balltrack.position_x
    actual_y = balltrack.position_y
    expected_distance = math.sqrt((client_coordinate["x"] - actual_x) ** 2 + (client_coordinate["y"] - actual_y) ** 2)
    distance = server.compute_error(balltrack, client_coordinate)
    assert distance == expected_distance


if __name__ == "__main__":
    pytest.main()
