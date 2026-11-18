"""
ADVANCED INTERACTIVE QR CODE GENERATOR
======================================
Run:
    python qr_codes/qr_generator.py

No Python? The same tool runs in the browser, nothing to install:
    https://elfarchouni.github.io/everyday-python-toolbox/qr/

The program will ask you for:
- URL / text
- QR module shape
- Eye shape
- Colors
- Optional logo
- Resolution
- Border
- Output format
- Filename

Outputs:
- High-resolution PNG
- SVG
- or both

Required packages are checked automatically.
"""

import sys
import subprocess
import importlib.util
from pathlib import Path


# ============================================================
# 1. AUTOMATIC PACKAGE INSTALLATION
# ============================================================

REQUIRED_PACKAGES = {
    "qrcode": "qrcode[pil]",
    "PIL": "Pillow",
}


def ensure_packages():
    print("\nChecking required packages...")

    for module, package in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(module) is None:
            print(f"Installing {package}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package]
            )

    print("✓ Required packages are ready.\n")


ensure_packages()


# ============================================================
# 2. IMPORTS
# ============================================================

import qrcode
import qrcode.image.svg

from PIL import ImageColor

from qrcode.constants import (
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
    ERROR_CORRECT_H,
)

from qrcode.image.styledpil import StyledPilImage

from qrcode.image.styles.moduledrawers.pil import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
    VerticalBarsDrawer,
    HorizontalBarsDrawer,
)

from qrcode.image.styles.colormasks import (
    SolidFillColorMask,
    RadialGradiantColorMask,
    SquareGradiantColorMask,
    HorizontalGradiantColorMask,
    VerticalGradiantColorMask,
)


# ============================================================
# 3. SMALL HELPER FUNCTIONS
# ============================================================

def line():
    print("=" * 65)


def title(text):
    print()
    line()
    print(text)
    line()


def ask_number(prompt, minimum, maximum, default=None):

    while True:

        if default is not None:
            value = input(f"{prompt} [{default}]: ").strip()

            if value == "":
                return default
        else:
            value = input(prompt).strip()

        try:
            value = int(value)

            if minimum <= value <= maximum:
                return value

            print(f"Please enter a number between {minimum} and {maximum}.")

        except ValueError:
            print("Please enter a valid number.")


def ask_yes_no(prompt, default="n"):

    while True:

        answer = input(prompt).strip().lower()

        if answer == "":
            answer = default

        if answer in ["y", "yes"]:
            return True

        if answer in ["n", "no"]:
            return False

        print("Please enter Y or N.")


def valid_color(color):

    try:
        ImageColor.getrgb(color)
        return True

    except ValueError:
        return False


def ask_color(prompt, default):

    while True:

        value = input(f"{prompt} [{default}]: ").strip()

        if not value:
            return default

        if valid_color(value):
            return value

        print(
            "Invalid color. Examples: black, white, navy, "
            "#003366, #1F4E79"
        )


def rgb(color):

    value = ImageColor.getrgb(color)

    if len(value) == 4:
        return value[:3]

    return value


# ============================================================
# 4. GET CONTENT
# ============================================================

def get_content():

    title("STEP 1 - QR CONTENT")

    while True:

        content = input(
            "\nPaste your URL, DOI, website, text, email, etc.:\n> "
        ).strip()

        if content:
            return content

        print("The QR content cannot be empty.")


# ============================================================
# 5. ERROR CORRECTION
# ============================================================

def choose_error_correction():

    title("STEP 2 - ERROR CORRECTION")

    print("""
1. L   ~7% recovery
2. M   ~15% recovery
3. Q   ~25% recovery
4. H   ~30% recovery  ← Recommended, especially with logo
""")

    choice = ask_number("Choose [1-4]", 1, 4, 4)

    levels = {
        1: ERROR_CORRECT_L,
        2: ERROR_CORRECT_M,
        3: ERROR_CORRECT_Q,
        4: ERROR_CORRECT_H,
    }

    return levels[choice]


# ============================================================
# 6. MODULE STYLE
# ============================================================

def choose_module_style():

    title("STEP 3 - QR SHAPE / STYLE")

    print("""
1. Classic Square
2. Rounded
3. Circular Dots
4. Gapped Squares
5. Vertical Bars
6. Horizontal Bars
""")

    choice = ask_number("Choose style [1-6]", 1, 6, 2)

    styles = {
        1: ("Classic Square", SquareModuleDrawer()),
        2: ("Rounded", RoundedModuleDrawer()),
        3: ("Circular Dots", CircleModuleDrawer()),
        4: ("Gapped Squares", GappedSquareModuleDrawer()),
        5: ("Vertical Bars", VerticalBarsDrawer()),
        6: ("Horizontal Bars", HorizontalBarsDrawer()),
    }

    return styles[choice]


# ============================================================
# 6b. EYE STYLE
# ============================================================

def choose_eye_style():

    title("STEP 4 - EYE (CORNER) SHAPE")

    print("""
1. Square (classic)
2. Rounded
3. Circular Dots
""")

    choice = ask_number("Choose eye shape [1-3]", 1, 3, 1)

    styles = {
        1: ("Square", SquareModuleDrawer()),
        2: ("Rounded", RoundedModuleDrawer()),
        3: ("Circular Dots", CircleModuleDrawer()),
    }

    return styles[choice]


# ============================================================
# 7. COLOR STYLE
# ============================================================

def choose_color_style():

    title("STEP 5 - COLOR DESIGN")

    print("""
1. Solid color
2. Radial gradient
3. Square gradient
4. Horizontal gradient
5. Vertical gradient
""")

    choice = ask_number("Choose [1-5]", 1, 5, 1)

    background = ask_color(
        "\nBackground color",
        "white"
    )

    if choice == 1:

        foreground = ask_color(
            "QR foreground color",
            "black"
        )

        mask = SolidFillColorMask(
            back_color=rgb(background),
            front_color=rgb(foreground),
        )

        description = f"Solid {foreground}"

    else:

        print("\nChoose the gradient colors.")

        color1 = ask_color(
            "Center / starting color",
            "#000000"
        )

        color2 = ask_color(
            "Outer / ending color",
            "#1F4E79"
        )

        if choice == 2:

            mask = RadialGradiantColorMask(
                back_color=rgb(background),
                center_color=rgb(color1),
                edge_color=rgb(color2),
            )

            description = "Radial gradient"

        elif choice == 3:

            mask = SquareGradiantColorMask(
                back_color=rgb(background),
                center_color=rgb(color1),
                edge_color=rgb(color2),
            )

            description = "Square gradient"

        elif choice == 4:

            mask = HorizontalGradiantColorMask(
                back_color=rgb(background),
                left_color=rgb(color1),
                right_color=rgb(color2),
            )

            description = "Horizontal gradient"

        else:

            mask = VerticalGradiantColorMask(
                back_color=rgb(background),
                top_color=rgb(color1),
                bottom_color=rgb(color2),
            )

            description = "Vertical gradient"

    return mask, description, background


# ============================================================
# 8. OPTIONAL LOGO
# ============================================================

def choose_logo():

    title("STEP 6 - LOGO")

    use_logo = ask_yes_no(
        "Add a logo/image in the center? [y/N]: ",
        "n"
    )

    if not use_logo:
        return None

    while True:

        path_text = input(
            "\nDrag your PNG/JPG logo here or enter its path:\n> "
        ).strip()

        # Windows drag/drop can add quotes
        path_text = path_text.strip('"').strip("'")

        path = Path(path_text)

        if path.exists() and path.is_file():
            return path

        print("\nFile not found.")

        retry = ask_yes_no(
            "Try another path? [Y/n]: ",
            "y"
        )

        if not retry:
            return None


# ============================================================
# 9. SIZE AND BORDER
# ============================================================

def choose_size():

    title("STEP 7 - OUTPUT QUALITY")

    print("""
Recommended:

1. 1000 px   - Normal digital use
2. 2000 px   - High quality
3. 3000 px   - Poster / presentation
4. 4000 px   - Very high quality
5. Custom
""")

    choice = ask_number("Choose [1-5]", 1, 5, 3)

    sizes = {
        1: 1000,
        2: 2000,
        3: 3000,
        4: 4000,
    }

    if choice == 5:

        target_size = ask_number(
            "Enter desired width in pixels",
            500,
            10000,
            3000
        )

    else:
        target_size = sizes[choice]

    print("""
QR quiet-zone border:

4 modules is the standard recommended minimum.
""")

    border = ask_number(
        "Border size in modules",
        4,
        15,
        4
    )

    return target_size, border


# ============================================================
# 10. OUTPUT FORMAT
# ============================================================

def choose_format():

    title("STEP 8 - OUTPUT FORMAT")

    print("""
1. PNG
2. SVG
3. PNG + SVG
""")

    choice = ask_number("Choose [1-3]", 1, 3, 3)

    return choice


# ============================================================
# 11. OUTPUT NAME
# ============================================================

def choose_filename():

    title("STEP 9 - FILE NAME")

    filename = input(
        "Output filename [QR_Code]: "
    ).strip()

    if not filename:
        filename = "QR_Code"

    # Remove common extensions if user typed them
    for extension in [".png", ".svg", ".jpg", ".jpeg"]:
        if filename.lower().endswith(extension):
            filename = filename[:-len(extension)]

    # Sanitize Windows-invalid filename characters
    invalid = '<>:"/\\|?*'

    for character in invalid:
        filename = filename.replace(character, "_")

    return filename


# ============================================================
# 12. CREATE QR OBJECT
# ============================================================

def create_qr(content, correction, border, target_size):

    qr = qrcode.QRCode(
        version=None,
        error_correction=correction,
        box_size=20,
        border=border,
    )

    qr.add_data(content)

    qr.make(fit=True)

    # Pixels per module so the natural render lands as close as
    # possible to the requested resolution while keeping every
    # module exactly the same width (no resampling distortion)
    total_modules = qr.modules_count + 2 * border

    qr.box_size = max(1, target_size // total_modules)

    return qr


# ============================================================
# 13. GENERATE PNG
# ============================================================

def generate_png(
    qr,
    module_drawer,
    eye_drawer,
    color_mask,
    logo,
    output_path
):

    kwargs = {
        "image_factory": StyledPilImage,
        "module_drawer": module_drawer,
        "eye_drawer": eye_drawer,
        "color_mask": color_mask,
    }

    if logo is not None:
        kwargs["embedded_image_path"] = str(logo)

    image = qr.make_image(**kwargs)

    image = image.convert("RGB")

    image.save(
        output_path,
        "PNG",
        optimize=True,
        dpi=(300, 300)
    )

    print(f"PNG rendered at {image.width} × {image.height} px.")

    return output_path


# ============================================================
# 14. GENERATE SVG
# ============================================================

def generate_svg(
    content,
    correction,
    border,
    output_path
):

    """
    SVG is intentionally generated using a classic vector QR.

    This gives a highly reliable scalable version suitable for:
    Adobe Illustrator
    Inkscape
    PowerPoint
    Posters
    Publications
    """

    factory = qrcode.image.svg.SvgPathImage

    qr = qrcode.QRCode(
        version=None,
        error_correction=correction,
        box_size=10,
        border=border,
    )

    qr.add_data(content)

    qr.make(fit=True)

    image = qr.make_image(
        image_factory=factory
    )

    image.save(str(output_path))

    return output_path


# ============================================================
# 15. MAIN PROGRAM
# ============================================================

def main():

    print("\n")
    line()
    print("     ADVANCED INTERACTIVE QR CODE GENERATOR")
    line()

    print("""
This tool creates professional QR codes for:

• Websites
• DOI links
• Research articles
• GitHub repositories
• Posters
• Presentations
• LinkedIn
• Portfolios
• Google Drive links
• Any URL or text
""")

    # --------------------------------------------------------
    # Collect options
    # --------------------------------------------------------

    content = get_content()

    correction = choose_error_correction()

    style_name, module_drawer = choose_module_style()

    eye_name, eye_drawer = choose_eye_style()

    color_mask, color_description, background = choose_color_style()

    logo = choose_logo()

    target_size, border = choose_size()

    output_format = choose_format()

    filename = choose_filename()

    # --------------------------------------------------------
    # Output folder
    # --------------------------------------------------------

    # Output goes next to this script, no matter where it is run from
    output_folder = Path(__file__).resolve().parent / "Generated_QR_Codes"

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Summary before generation
    # --------------------------------------------------------

    title("QR DESIGN SUMMARY")

    print(f"""
Content:
{content}

Module style:
{style_name}

Eye shape:
{eye_name}

Color design:
{color_description}

Background:
{background}

Logo:
{logo if logo else "No logo"}

PNG resolution:
~{target_size} × {target_size} px (rounded to uniform QR modules)

Border:
{border} modules

Output folder:
{output_folder}
""")

    proceed = ask_yes_no(
        "Generate this QR code? [Y/n]: ",
        "y"
    )

    if not proceed:
        print("\nGeneration cancelled.")
        return

    # --------------------------------------------------------
    # Build QR
    # --------------------------------------------------------

    print("\nGenerating QR code...")

    qr = create_qr(
        content,
        correction,
        border,
        target_size
    )

    created_files = []

    # PNG
    if output_format in [1, 3]:

        png_path = output_folder / f"{filename}.png"

        generate_png(
            qr,
            module_drawer,
            eye_drawer,
            color_mask,
            logo,
            png_path
        )

        created_files.append(png_path)

    # SVG
    if output_format in [2, 3]:

        svg_path = output_folder / f"{filename}.svg"

        generate_svg(
            content,
            correction,
            border,
            svg_path
        )

        created_files.append(svg_path)

        print(
            "Note: the SVG is exported in classic black-and-white\n"
            "(square modules, no logo) for maximum scan reliability\n"
            "and compatibility with vector editors."
        )

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    title("✓ QR CODE GENERATED SUCCESSFULLY")

    print("Created files:\n")

    for file in created_files:
        print(f"✓ {file}")

    print("""
-------------------------------------------------------------
IMPORTANT FOR PRINTING
-------------------------------------------------------------

For Adobe Illustrator:
    Prefer the SVG version.

For PowerPoint:
    SVG is recommended.

For posters:
    SVG is recommended because it is vector-based.

For websites/social media:
    PNG is normally best.

For QR codes with logos:
    Error correction H is recommended.

Always test the final QR code with your phone before printing.
""")

    # --------------------------------------------------------
    # Open output folder
    # --------------------------------------------------------

    if ask_yes_no(
        "Open the output folder now? [Y/n]: ",
        "y"
    ):

        try:

            import os
            import platform

            system = platform.system()

            if system == "Windows":
                os.startfile(output_folder)

            elif system == "Darwin":
                subprocess.run(
                    ["open", str(output_folder)]
                )

            else:
                subprocess.run(
                    ["xdg-open", str(output_folder)]
                )

        except Exception as error:
            print(
                f"\nCould not automatically open folder: {error}"
            )

    print("\nDone.\n")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print("\n\nProgram cancelled by user.")

    except Exception as error:
        print("\nAn error occurred:")
        print(error)

        input("\nPress ENTER to close...")