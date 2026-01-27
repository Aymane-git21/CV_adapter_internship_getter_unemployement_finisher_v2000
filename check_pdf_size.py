import re

def get_pdf_page_size(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            content = f.read()
            # Look for /MediaBox [0 0 width height]
            # This is a rough check, might not work for compressed PDFs or object streams
            match = re.search(rb'/MediaBox\s*\[\s*([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s*\]', content)
            if match:
                x1, y1, x2, y2 = map(float, match.groups())
                width_pt = x2 - x1
                height_pt = y2 - y1
                width_cm = width_pt * 2.54 / 72
                height_cm = height_pt * 2.54 / 72
                return width_cm, height_cm
            else:
                return None, None
    except Exception as e:
        print(f"Error: {e}")
        return None, None

pdf_path = r"c:\Users\ayman\Desktop\CV_adapter\CoverLetter.pdf"
w, h = get_pdf_page_size(pdf_path)
if w:
    print(f"PDF Size: {w:.2f}cm x {h:.2f}cm")
else:
    print("Could not determine PDF size via regex.")
