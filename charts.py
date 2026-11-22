from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac", "#eeca3b"]
SCALE = 2
WIDTH = 900
TEXT = "#222222"
GRID = "#dddddd"


def font(size):
    return ImageFont.load_default(size=size * SCALE)


def short(label, limit=30):
    label = str(label)
    return label if len(label) <= limit else label[: limit - 1] + "..."


def canvas(height):
    image = Image.new("RGB", (WIDTH * SCALE, int(height * SCALE)), "white")
    return image, ImageDraw.Draw(image)


def finish(image):
    small = image.resize((WIDTH, image.height // SCALE), Image.LANCZOS)
    buffer = BytesIO()
    small.save(buffer, format="PNG")
    return buffer.getvalue()


def text_width(draw, text, f):
    return draw.textlength(text, font=f) / SCALE


def put(draw, x, y, text, f, fill=TEXT, anchor="la"):
    draw.text((x * SCALE, y * SCALE), text, font=f, fill=fill, anchor=anchor)


def rect(draw, x0, y0, x1, y1, fill):
    draw.rectangle([x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE], fill=fill)


def nice_label(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def bar_png(labels, values, title):
    labels = [short(label) for label in labels]
    values = [float(v) for v in values]
    if not labels or max(values) <= 0:
        return None
    label_font, title_font = font(15), font(19)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    left = max(text_width(probe, label, label_font) for label in labels) + 30
    row = 34
    top = 56
    height = top + row * len(labels) + 24
    image, draw = canvas(height)
    put(draw, 20, 14, title, title_font)
    right_pad = 80
    plot = WIDTH - left - right_pad
    biggest = max(values)
    for i, (label, value) in enumerate(zip(labels, values)):
        y = top + i * row
        put(draw, left - 10, y + row / 2, label, label_font, anchor="rm")
        length = plot * value / biggest
        rect(draw, left, y + 5, left + max(length, 1), y + row - 5, PALETTE[0])
        put(draw, left + length + 8, y + row / 2, nice_label(value), label_font, anchor="lm")
    draw.line([left * SCALE, top * SCALE, left * SCALE, (top + row * len(labels)) * SCALE], fill="#888888", width=SCALE)
    return finish(image)


def grouped_bar_png(table, title):
    groups = [short(g) for g in table.index]
    series = [short(c, 20) for c in table.columns]
    values = table.values.astype(float)
    if values.size == 0 or values.max() <= 0:
        return None
    label_font, title_font = font(15), font(19)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    left = max(text_width(probe, g, label_font) for g in groups) + 30
    bar = 20
    gap = 14
    group_height = bar * len(series) + gap
    top = 92
    height = top + group_height * len(groups) + 16
    image, draw = canvas(height)
    put(draw, 20, 14, title, title_font)
    x = 20
    for i, name in enumerate(series):
        colour = PALETTE[i % len(PALETTE)]
        rect(draw, x, 56, x + 16, 72, colour)
        put(draw, x + 22, 64, name, label_font, anchor="lm")
        x += 22 + text_width(probe, name, label_font) + 24
    plot = WIDTH - left - 80
    biggest = values.max()
    for gi, group in enumerate(groups):
        y = top + gi * group_height
        put(draw, left - 10, y + (bar * len(series)) / 2, group, label_font, anchor="rm")
        for si in range(len(series)):
            value = values[gi][si]
            length = plot * value / biggest
            y0 = y + si * bar
            rect(draw, left, y0 + 2, left + max(length, 1), y0 + bar - 2, PALETTE[si % len(PALETTE)])
            put(draw, left + length + 8, y0 + bar / 2, nice_label(value), label_font, anchor="lm")
    draw.line([left * SCALE, top * SCALE, left * SCALE, (top + group_height * len(groups) - gap) * SCALE], fill="#888888", width=SCALE)
    return finish(image)


def pyramid_png(table, title):
    groups = [short(g) for g in table.index]
    names = [short(c, 20) for c in table.columns]
    values = table.values.astype(float)
    if values.shape[1] != 2 or values.max() <= 0:
        return None
    label_font, title_font = font(15), font(19)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    middle = max(text_width(probe, g, label_font) for g in groups) + 30
    side = (WIDTH - middle - 60) / 2
    row = 32
    top = 92
    height = top + row * len(groups) + 20
    image, draw = canvas(height)
    put(draw, 20, 14, title, title_font)
    centre_left = 30 + side
    centre_right = centre_left + middle
    left_colour, right_colour = "#4c78a8", "#f58518"
    rect(draw, 20, 56, 36, 72, left_colour)
    put(draw, 42, 64, names[0], label_font, anchor="lm")
    x = 42 + text_width(probe, names[0], label_font) + 30
    rect(draw, x, 56, x + 16, 72, right_colour)
    put(draw, x + 22, 64, names[1], label_font, anchor="lm")
    biggest = values.max()
    count = len(groups)
    for i, group in enumerate(groups):
        y = top + (count - 1 - i) * row
        put(draw, (centre_left + centre_right) / 2, y + row / 2, group, label_font, anchor="mm")
        left_len = side * values[i][0] / biggest
        right_len = side * values[i][1] / biggest
        if values[i][0] > 0:
            rect(draw, centre_left - left_len, y + 4, centre_left, y + row - 4, left_colour)
            put(draw, centre_left - left_len - 6, y + row / 2, nice_label(values[i][0]), label_font, anchor="rm")
        if values[i][1] > 0:
            rect(draw, centre_right, y + 4, centre_right + right_len, y + row - 4, right_colour)
            put(draw, centre_right + right_len + 6, y + row / 2, nice_label(values[i][1]), label_font, anchor="lm")
    return finish(image)


def pie_png(labels, values, title):
    labels = [short(label, 26) for label in labels]
    values = [float(v) for v in values]
    total = sum(values)
    if total <= 0:
        return None
    label_font, title_font = font(15), font(19)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = 300
    height = 56 + max(size, 40 * len(labels)) + 30
    image, draw = canvas(height)
    put(draw, 20, 14, title, title_font)
    box = [30 * SCALE, 64 * SCALE, (30 + size) * SCALE, (64 + size) * SCALE]
    start = -90.0
    for i, value in enumerate(values):
        if value <= 0:
            continue
        sweep = 360.0 * value / total
        draw.pieslice(box, start, start + sweep, fill=PALETTE[i % len(PALETTE)], outline="white", width=2 * SCALE)
        start += sweep
    x = 30 + size + 50
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 80 + i * 40
        rect(draw, x, y, x + 18, y + 18, PALETTE[i % len(PALETTE)])
        put(draw, x + 28, y + 9, f"{label}: {nice_label(value)} ({value / total * 100:.1f}%)", label_font, anchor="lm")
    return finish(image)
