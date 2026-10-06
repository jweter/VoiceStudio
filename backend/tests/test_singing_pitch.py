import pytest

from services.singing_pitch import F0Frame, F0Track


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
    with pytest.raises(ValueError, match="unvoiced"):
        F0Frame(0.0, 220.0, False, 0.5)


def test_timestamps_must_be_strictly_increasing() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        F0Track(
            48000,
            480,
            (
                F0Frame(0.1, 220.0, True, 1.0),
                F0Frame(0.1, 221.0, True, 1.0),
            ),
        )


def test_from_dict_rejects_coercible_wrong_types() -> None:
    payload = F0Track(48000, 480, (F0Frame(0.0, 220.0, True, 0.9),)).to_dict()
    payload["sample_rate"] = 48000.9
    with pytest.raises(ValueError, match="integers"):
        F0Track.from_dict(payload)

    payload = F0Track(48000, 480, (F0Frame(0.0, 220.0, True, 0.9),)).to_dict()
    payload["hop_samples"] = True
    with pytest.raises(ValueError, match="integers"):
        F0Track.from_dict(payload)

    payload = F0Track(48000, 480, (F0Frame(0.0, 220.0, True, 0.9),)).to_dict()
    payload["frames"][0]["voiced"] = "false"
    with pytest.raises(ValueError, match="boolean"):
        F0Track.from_dict(payload)


def test_extract_f0_tracks_known_two_note_melody() -> None:
    import numpy as np
    from services.singing_pitch import extract_f0

    sample_rate = 48000
    seconds = 0.25
    t = np.arange(int(sample_rate * seconds), dtype=np.float64) / sample_rate
    a3 = 0.5 * np.sin(2 * np.pi * 220.0 * t)
    a4 = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    audio = np.concatenate((a3, a4))

    track = extract_f0(
        audio,
        sample_rate,
        hop_samples=2400,
        frame_samples=4096,
        min_hz=100.0,
        max_hz=600.0,
        voicing_threshold=0.5,
    )
    voiced = [frame.frequency_hz for frame in track.frames if frame.voiced]
    assert any(freq is not None and abs(freq - 220.0) < 5.0 for freq in voiced[:5])
    assert any(freq is not None and abs(freq - 440.0) < 8.0 for freq in voiced[5:])
