import re
import zipfile
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_RELS_START = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="44"/><w:szCs w:val="44"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="200" w:after="60"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/><w:szCs w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="160" w:after="60"/></w:pPr><w:rPr><w:b/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>
<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:uiPriority w:val="99"/><w:semiHidden/>
<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/>
<w:tblPr><w:tblBorders>
<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/>
<w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/>
<w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/>
</w:tblBorders></w:tblPr></w:style>
</w:styles>"""

BAD_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text):
    return escape(BAD_CHARS.sub("", str(text)))


def run(text, bold=False, italic=False, size=None):
    props = ""
    if bold:
        props += "<w:b/>"
    if italic:
        props += "<w:i/>"
    if size:
        props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    if props:
        props = f"<w:rPr>{props}</w:rPr>"
    return f'<w:r>{props}<w:t xml:space="preserve">{clean(text)}</w:t></w:r>'


def paragraph(text, style=None, bold=False, italic=False, align=None):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if align:
        ppr += f'<w:jc w:val="{align}"/>'
    if ppr:
        ppr = f"<w:pPr>{ppr}</w:pPr>"
    return f"<w:p>{ppr}{run(text, bold=bold, italic=italic)}</w:p>"


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def table_xml(table):
    frame = table.reset_index()
    first = frame.columns[0]
    headers = ["" if first in ("index", None) else str(first)] + [str(c) for c in frame.columns[1:]]
    columns = len(headers)
    total = 9638
    if columns > 2:
        first_width = int(total * 0.24)
        width = (total - first_width) // (columns - 1)
        widths = [first_width] + [width] * (columns - 1)
    else:
        widths = [total // max(columns, 1)] * columns
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    rows = []
    head = "".join(
        f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>{run(h, bold=True, size=20)}</w:p></w:tc>'
        for h, w in zip(headers, widths)
    )
    rows.append(f'<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>{head}</w:tr>')
    for _, row in frame.iterrows():
        cells = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>{run(cell_text(v), size=20)}</w:p></w:tc>'
            for v, w in zip(row.tolist(), widths)
        )
        rows.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>")
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>"
        '<w:p><w:pPr><w:spacing w:after="60"/></w:pPr></w:p>'
    )


def image_xml(number, rid, png, caption):
    from PIL import Image

    pixel_width, pixel_height = Image.open(BytesIO(png)).size
    cx = 5486400
    cy = int(cx * pixel_height / pixel_width)
    return (
        "<w:p><w:pPr><w:spacing w:after=\"120\"/></w:pPr><w:r><w:drawing>"
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{number}" name="Chart {number}" descr="{clean(caption)}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{number}" name="chart{number}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


def build_docx(title, topic, blocks):
    images = []
    body = [paragraph(title, style="Title")]
    if topic:
        body.append(paragraph(f"Research topic: {topic}", bold=True))
    body.append(paragraph(f"Prepared on {date.today().strftime('%d %B %Y')} with Research Data Check.", italic=True))
    for block in blocks:
        kind = block[0]
        if kind == "h1":
            body.append(paragraph(block[1], style="Heading1"))
        elif kind == "h2":
            body.append(paragraph(block[1], style="Heading2"))
        elif kind == "h3":
            body.append(paragraph(block[1], style="Heading3"))
        elif kind == "text":
            body.append(paragraph(block[1]))
        elif kind == "note":
            body.append(paragraph(block[1], italic=True))
        elif kind == "caption":
            body.append(paragraph(block[1], style="Caption"))
        elif kind == "table":
            if block[1]:
                body.append(paragraph(block[1], style="Caption"))
            body.append(table_xml(block[2]))
        elif kind == "image":
            if block[2]:
                images.append(block[2])
                number = len(images)
                if block[1]:
                    body.append(paragraph(block[1], style="Caption"))
                body.append(image_xml(number, f"rId{number + 1}", block[2], block[1]))
    section = (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        f"<w:body>{''.join(body)}{section}</w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        rels = DOCUMENT_RELS_START
        for number in range(1, len(images) + 1):
            rels += (
                f'<Relationship Id="rId{number + 1}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="media/image{number}.png"/>'
            )
        rels += "</Relationships>"
        z.writestr("word/_rels/document.xml.rels", rels)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/document.xml", document)
        for number, png in enumerate(images, start=1):
            z.writestr(f"word/media/image{number}.png", png)
    return buffer.getvalue()
