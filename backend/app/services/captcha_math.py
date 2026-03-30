import base64
import random
import uuid
from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from loguru import logger

from app.core.constants import CAPTCHA_TTL
from app.core.redis import get_redis

# ---------------------------------------------------------------------------
# Calculus problem templates — each returns (latex_str, int_answer)
# ---------------------------------------------------------------------------

def _integral_poly() -> tuple[str, int]:
    """∫_a^b c·x^n dx with integer result."""
    n = random.choice([1, 2, 3])
    divisor = n + 1
    a = random.randint(0, 3)
    b = random.randint(a + 1, a + 3)
    # Pick c as a multiple of divisor so the answer is always an integer
    c = random.choice([i for i in range(1, 7) if i % divisor == 0] or [divisor])
    answer = c * (b ** divisor - a ** divisor) // divisor
    if c == 1:
        latex = rf"\int_{{{a}}}^{{{b}}} x^{{{n}}} \, dx"
    else:
        latex = rf"\int_{{{a}}}^{{{b}}} {c}x^{{{n}}} \, dx"
    return latex, answer


def _derivative_at_point() -> tuple[str, int]:
    """d/dx(c·x^n) evaluated at x=k."""
    n = random.choice([2, 3, 4])
    c = random.randint(1, 5)
    k = random.randint(1, 3)
    answer = c * n * k ** (n - 1)
    if c == 1:
        body = rf"x^{{{n}}}"
    else:
        body = rf"{c}x^{{{n}}}"
    latex = rf"\left.\frac{{d}}{{dx}}\left({body}\right)\right|_{{x={k}}}"
    return latex, answer


def _limit_cancel() -> tuple[str, int]:
    """lim_{x→a} (x²-a²)/(x-a) = 2a."""
    a = random.randint(1, 10)
    answer = 2 * a
    latex = rf"\lim_{{x \to {a}}} \frac{{x^2 - {a ** 2}}}{{x - {a}}}"
    return latex, answer


def _polynomial_eval() -> tuple[str, int]:
    """f(x)=ax²+bx+c, find f(k)."""
    a = random.randint(1, 4)
    b = random.randint(-5, 5)
    c = random.randint(-8, 8)
    k = random.randint(-3, 3)
    answer = a * k * k + b * k + c

    terms = []
    if a == 1:
        terms.append("x^{2}")
    else:
        terms.append(rf"{a}x^{{2}}")
    if b > 0:
        terms.append(rf"+{b}x" if b != 1 else "+x")
    elif b < 0:
        terms.append(rf"{b}x" if b != -1 else "-x")
    if c > 0:
        terms.append(rf"+{c}")
    elif c < 0:
        terms.append(rf"{c}")

    expr = "".join(terms)
    latex = rf"f(x)={expr}, \quad f({k})"
    return latex, answer


def _second_derivative() -> tuple[str, int]:
    """d²/dx²(c·x^n) evaluated at x=k."""
    n = random.choice([3, 4])
    c = random.randint(1, 4)
    k = random.randint(1, 3)
    answer = c * n * (n - 1) * k ** (n - 2)
    if c == 1:
        body = rf"x^{{{n}}}"
    else:
        body = rf"{c}x^{{{n}}}"
    latex = rf"\left.\frac{{d^2}}{{dx^2}}\left({body}\right)\right|_{{x={k}}}"
    return latex, answer


_TEMPLATES = [
    _integral_poly,
    _derivative_at_point,
    _limit_cancel,
    _polynomial_eval,
    _second_derivative,
]


def _generate_problem() -> tuple[str, int]:
    """Pick a random template and generate a problem."""
    fn = random.choice(_TEMPLATES)
    return fn()


def _render_latex(latex: str) -> str:
    """Render a LaTeX expression to a base64-encoded PNG data URI."""
    fig, ax = plt.subplots(figsize=(4.5, 1.3), dpi=90)
    ax.text(
        0.5,
        0.5,
        rf"${latex} = \;?$",
        fontsize=18,
        ha="center",
        va="center",
        transform=ax.transAxes,
    )
    ax.axis("off")
    fig.patch.set_facecolor("white")

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)

    image_base64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return image_base64


async def generate_math_captcha() -> tuple[str, str]:
    """Generate a calculus captcha. Returns (captcha_id, image_base64)."""
    redis = get_redis()
    captcha_id = str(uuid.uuid4())

    latex, answer = _generate_problem()
    image_base64 = _render_latex(latex)

    # Store answer as string — verify_captcha compares strings
    await redis.set(f"captcha:{captcha_id}", str(answer), ex=CAPTCHA_TTL)
    logger.info("Math captcha generated", extra={"captcha_id": captcha_id})

    return captcha_id, image_base64
