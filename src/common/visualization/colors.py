"""Color utilities."""


def parse_hex_rgb(value: str) -> int:

    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("expected #RRGGBB")

    try:
        rgb = int(value[1:], 16)
    except ValueError as error:
        raise ValueError("expected #RRGGBB") from error

    return rgb


def mix_with_white(rgb: int, white_fraction: float) -> str:
    packed = 0
    for shift in (16, 8, 0):
        channel = (rgb >> shift) & 0xFF
        packed |= round(channel + (255 - channel) * white_fraction) << shift
    return f"#{packed:06x}"


def tint(base_hex: str, white_fraction: float) -> str:
    """Return ``base_hex`` mixed with white.
    ``white_fraction`` is 0 for the base, 1 for white.
    """

    if not 0 <= white_fraction <= 1:
        raise ValueError("white_fraction must be between 0 and 1")

    rgb = parse_hex_rgb(base_hex)
    return mix_with_white(rgb, white_fraction)


def hex_tints(
    base_hex: str,
    n_colors: int,
    *,
    lightest_white: float = 0.75,
) -> list[str]:
    """Return ``n_colors`` hex values from a light tint down to ``base_hex``.

    ``lightest_white`` is the fraction of white mixed into the first color
    (0 is the base, 1 is white). The last color is always the base.
    """

    if n_colors < 1:
        raise ValueError("n_colors must be at least 1")
    if not 0 <= lightest_white <= 1:
        raise ValueError("lightest_white must be between 0 and 1")

    rgb = parse_hex_rgb(base_hex)
    if n_colors == 1:
        white_fractions = [0.0]
    else:
        last_index = n_colors - 1
        white_fractions = [
            lightest_white * (1 - index / last_index) for index in range(n_colors)
        ]
    return [mix_with_white(rgb, wf) for wf in white_fractions]
