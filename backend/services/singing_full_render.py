"""Full-length singing render through the existing S4 conversion and duration contracts.

Unlike render_preview, this service never truncates the guide vocal. A caller
must provide a documented positive duration cap; the source of that policy is
the caller, never a model-authored literal or an invented 120-second threshold.
"""

from __future__ import annotations

from services.singing_conversion import (
    ConversionRequest,
    ConversionResult,
    InvalidConversionRequest,
    SingingConversionEngine,
    convert_singing,
    wav_duration_seconds,
)
from services.singing_render_limits import full_render_duration_error


def render_full_singing(
    engine: SingingConversionEngine,
    request: ConversionRequest,
    *,
    max_seconds: object,
) -> ConversionResult:
    """Convert the complete guide into the S2 project's renders/vocal_full.wav.

    The configured cap is enforced before conversion and yields the exact
    existing full_render_duration_error message. Engine eligibility, output
    containment, timestamp drift, and synthetic-audio provenance remain in
    convert_singing; there is no speech fallback or second conversion path.
    """
    if request.output_name != "vocal_full.wav":
        raise InvalidConversionRequest(
            "full singing renders must write the project's vocal_full.wav"
        )
    guide_seconds, _sample_rate = wav_duration_seconds(request.guide_vocal)
    problem = full_render_duration_error(guide_seconds, max_seconds)
    if problem is not None:
        raise InvalidConversionRequest(problem)
    return convert_singing(engine, request)
