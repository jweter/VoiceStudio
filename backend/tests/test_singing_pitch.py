from backend.services.singing_pitch import F0Frame, F0Track


def test_f0_track_round_trip_is_deterministic() -> None:
    track = F0Track(
        sample_rate=48000,
        hop_samples=480,
        frames=(
            F0Frame(0.0, 220.0, True, 0.99),
            F0Frame(0.01, None, False, 0.8),
            F0Frame(0.02, 440.0, True, 0.95),
        ),
    )
    assert F0Track.from_dict(track.to_dict()) == track
    assert F0Track.from_dict(track.to_dict()).to_json() == track.to_json()


def test_unvoiced_frame_cannot_smuggle_pitch() -> None:
    import pytest
    with pytest.raises(ValueError, match="unvoiced"):
        F0Frame(0.0, 220.0, False, 0.5)


def test_timestamps_must_be_strictly_increasing() -> None:
    import pytest
    with pytest.raises(ValueError, match="strictly increasing"):
        F0Track(48000, 480, (F0Frame(0.1, 220.0, True, 1.0), F0Frame(0.1, 221.0, True, 1.0)))
