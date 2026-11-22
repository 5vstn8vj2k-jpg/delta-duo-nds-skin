#!/usr/bin/env python3
"""Validate a Delta Emulator .deltaskin ZIP without modifying it.

Only the Python standard library and Pillow are required.  Exit status is 1
when errors are found and 0 for a clean or warning-only validation.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - gives a useful CLI error
    Image = None  # type: ignore

GAME_TYPE = "com.rileytestut.delta.game.ds"
DIRECTIONS = ("portrait", "landscape")
REQUIRED_BUTTONS = {"up", "down", "left", "right", "a", "b", "x", "y", "l", "r", "start", "select", "menu"}
SCREEN_SIZE = (256, 192)


class Validator:
    def __init__(self, archive: str):
        self.archive = archive
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.names: set[str] = set()
        self.data: dict[str, Any] | None = None
        self.zf: zipfile.ZipFile | None = None

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def run(self) -> int:
        try:
            self.zf = zipfile.ZipFile(self.archive)
        except (OSError, zipfile.BadZipFile) as exc:
            self.error(f"cannot open ZIP: {exc}")
            return self.report()
        try:
            infos = self.zf.infolist()
            self.names = {i.filename for i in infos}
            if len(self.names) != len(infos):
                self.error("archive contains duplicate member names")
            self.check_info()
            if self.data is not None:
                self.check_document()
        finally:
            self.zf.close()
        return self.report()

    def check_info(self) -> None:
        assert self.zf is not None
        if "info.json" not in self.names:
            self.error("archive root is missing info.json")
            return
        try:
            raw = self.zf.read("info.json")
            value = json.loads(raw.decode("utf-8"))
        except KeyError:
            self.error("cannot read root info.json")
            return
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.error(f"info.json is not valid UTF-8 JSON: {exc}")
            return
        if not isinstance(value, dict):
            self.error("root info.json must contain a JSON object")
            return
        self.data = value

    def check_document(self) -> None:
        assert self.data is not None
        if self.data.get("gameTypeIdentifier") != GAME_TYPE:
            self.error(f"gameTypeIdentifier must be {GAME_TYPE!r}")
        identifier = self.data.get("identifier")
        if not isinstance(identifier, str) or not identifier.strip():
            self.error("root identifier must be a non-empty string")
        name = self.data.get("name")
        if not isinstance(name, str) or not name.strip():
            self.error("root name must be a non-empty string")

        reps = self.data.get("representations")
        if not isinstance(reps, dict):
            self.error("representations must be an object")
            return
        iphone = reps.get("iphone")
        if not isinstance(iphone, dict):
            self.error("representations.iphone is required for Duo skins")
            return

        usable_duo = 0
        # Only iPhone Duo inner/outer are required. Other device keys are not
        # treated as Duo layouts and must not acquire artificial requirements.
        for layout in ("inner", "outer"):
            section = iphone.get(layout)
            if section is None:
                self.warn(f"representations.iphone.{layout} is missing; Duo coverage is incomplete")
                continue
            if not isinstance(section, dict):
                self.warn(f"representations.iphone.{layout} is not an object; Duo coverage is incomplete")
                continue
            present = 0
            for direction in DIRECTIONS:
                view = section.get(direction)
                if view is None:
                    self.warn(f"representations.iphone.{layout}.{direction} is missing; Duo coverage is incomplete")
                elif not isinstance(view, dict):
                    self.warn(f"representations.iphone.{layout}.{direction} is not an object; Duo coverage is incomplete")
                else:
                    present += 1
                    self.check_view(f"representations.iphone.{layout}.{direction}", view, require_screens=True)
            usable_duo += present
        if usable_duo == 0:
            self.error("representations.iphone has no usable Duo inner/outer direction")

        # These are optional iPhone modes. cover intentionally has no screens;
        # splitView may use an app-placement screen for the upper display.
        for layout in ("splitView", "cover"):
            section = iphone.get(layout)
            if section is None:
                continue
            if not isinstance(section, dict):
                self.error(f"representations.iphone.{layout} must be an object")
                continue
            for direction, view in section.items():
                path = f"representations.iphone.{layout}.{direction}"
                if not isinstance(view, dict):
                    self.error(f"{path} must be an object")
                elif layout == "cover":
                    self.check_assets(path, view)
                else:
                    self.check_view(path, view, require_screens=True, placement_exceptions=True)

    def check_assets(self, path: str, view: dict[str, Any]) -> None:
        assets = view.get("assets")
        if not isinstance(assets, dict):
            self.error(f"{path}.assets is missing or not an object")
            return
        for kind, filename in assets.items():
            if not isinstance(filename, str) or not filename:
                self.error(f"{path}.assets.{kind} must be a filename")
                continue
            # Resource references are ZIP-root files, never nested paths.
            if "/" in filename or "\\" in filename or filename in (".", ".."):
                self.error(f"{path}.assets.{kind} must reference a root-level filename, not {filename!r}")
                continue
            if filename not in self.names:
                self.error(f"{path}.assets.{kind} references missing root file {filename!r}")
            if filename.lower().endswith(".png"):
                self.check_png(path, filename, view.get("mappingSize"), kind)

    def read_image(self, filename: str):
        assert self.zf is not None
        if Image is None:
            self.error("Pillow is required to inspect PNG dimensions")
            return None
        try:
            image = Image.open(io.BytesIO(self.zf.read(filename)))
            if image.format != "PNG":
                image.close()
                self.error(f"asset {filename!r} is not a PNG image")
                return None
            return image.convert("RGBA")
        except (KeyError, OSError, ValueError) as exc:
            self.error(f"cannot read image {filename!r}: {exc}")
            return None

    def check_png(self, path: str, filename: str, mapping: Any, kind: Any) -> None:
        image = self.read_image(filename)
        if image is None:
            return
        size = image.size
        image.close()
        # The conventional 3x check applies to the large asset only. Other
        # resource classes may use a different scale and are not guessed at.
        if kind != "large":
            return
        if not (isinstance(mapping, dict) and self.positive_pair(mapping, "width", "height")):
            return
        mw, mh = mapping["width"], mapping["height"]
        if size != (mw * 3, mh * 3):
            self.warn(f"{path}: {filename!r} is {size[0]}x{size[1]}, not the usual 3x mappingSize {mw * 3}x{mh * 3}")

    def check_view(self, path: str, view: dict[str, Any], require_screens: bool, placement_exceptions: bool = False) -> None:
        self.check_assets(path, view)
        mapping = view.get("mappingSize")
        if not isinstance(mapping, dict) or not self.positive_pair(mapping, "width", "height"):
            self.error(f"{path}.mappingSize must contain positive width and height")
            return
        canvas = (mapping["width"], mapping["height"])
        screens = view.get("screens")
        if require_screens and not isinstance(screens, list):
            self.error(f"{path}.screens must be an array")
            screens = []
        if not isinstance(screens, list):
            screens = []

        upper: dict[str, Any] | None = None
        lower: dict[str, Any] | None = None
        for index, screen in enumerate(screens):
            spath = f"{path}.screens[{index}]"
            if not isinstance(screen, dict):
                self.error(f"{spath} must be an object")
                continue
            inp = screen.get("inputFrame")
            if not self.valid_frame(inp):
                self.error(f"{spath}.inputFrame is invalid")
            else:
                input_rect = self.rect(inp)
                if input_rect == (0, 0, 256, 192):
                    upper = screen
                elif input_rect == (0, 192, 256, 384):
                    lower = screen
                else:
                    self.error(f"{spath}.inputFrame must be upper (0,0,256,192) or lower (0,192,256,192)")
            placement = screen.get("placement")
            output = screen.get("outputFrame")
            if placement == "app" and placement_exceptions:
                output = None
            elif output is None:
                self.error(f"{spath}.outputFrame is required")
            elif not self.valid_frame(output):
                self.error(f"{spath}.outputFrame is invalid")
            elif not self.inside(output, canvas):
                self.error(f"{spath}.outputFrame must be inside mappingSize canvas")
            elif abs(output["width"] / output["height"] - 4 / 3) > 0.02:
                self.warn(f"{spath}.outputFrame is not approximately 4:3; verify intended stretching")

        if require_screens:
            if upper is None:
                self.error(f"{path} is missing upper screen inputFrame (0,0,256,192)")
            if lower is None:
                self.error(f"{path} is missing lower screen inputFrame (0,192,256,192)")

        lower_output = self.rect(lower["outputFrame"]) if lower and self.valid_frame(lower.get("outputFrame")) else None
        upper_output = self.rect(upper["outputFrame"]) if upper and upper.get("placement") != "app" and self.valid_frame(upper.get("outputFrame")) else None
        assets = view.get("assets")
        output_pngs = [filename for kind, filename in assets.items() if kind == "large" and isinstance(filename, str) and filename.lower().endswith(".png")] if isinstance(assets, dict) else []
        if output_pngs:
            for filename in output_pngs:
                self.check_output_alpha(path, filename, view, upper, lower)

        items = view.get("items")
        if not isinstance(items, list):
            self.error(f"{path}.items must be an array")
            return
        seen_inputs: set[str] = set()
        touch_item: dict[str, Any] | None = None
        hotzones: list[tuple[str, tuple[float, float, float, float]]] = []
        for index, item in enumerate(items):
            ipath = f"{path}.items[{index}]"
            if not isinstance(item, dict):
                self.error(f"{ipath} must be an object")
                continue
            inputs = item.get("inputs")
            input_names: set[str] = set()
            if isinstance(inputs, list):
                if not inputs or not all(isinstance(x, str) and x for x in inputs):
                    self.error(f"{ipath}.inputs must be a non-empty string array")
                input_names = {x for x in inputs if isinstance(x, str)}
            elif isinstance(inputs, dict):
                if set(inputs) == {"x", "y"} and inputs.get("x") == "touchScreenX" and inputs.get("y") == "touchScreenY":
                    if touch_item is not None:
                        self.error(f"{path} has more than one touch-screen item")
                    touch_item = item
                elif set(inputs) == {"up", "down", "left", "right"} and all(isinstance(x, str) and x for x in inputs.values()):
                    input_names = set(inputs)
                else:
                    self.error(f"{ipath}.inputs object must map d-pad directions or touchScreenX/touchScreenY")
            else:
                self.error(f"{ipath}.inputs is missing or invalid")
            overlap = seen_inputs & input_names
            if overlap:
                self.error(f"{ipath}.inputs duplicates {sorted(overlap)}")
            seen_inputs.update(input_names)
            frame = item.get("frame")
            if not self.valid_frame(frame):
                self.error(f"{ipath}.frame must be a positive frame with numeric coordinates")
                continue
            effective = self.effective_edges(item.get("extendedEdges"), view.get("extendedEdges"), ipath)
            if effective is None:
                continue
            if touch_item is item and any(effective.values()):
                self.error(f"{ipath} touch extendedEdges must resolve to all zero")
            zone = self.expand(self.rect(frame), effective)
            hotzones.append((ipath, zone))
            if lower_output is not None and touch_item is not item and self.intersects(zone, lower_output):
                self.warn(f"{ipath} non-touch control extended region intersects lower-screen output")
            if upper_output is not None and self.intersects(zone, upper_output):
                self.warn(f"{ipath} control extended region intersects upper-screen output")

        for i, (left_path, left_zone) in enumerate(hotzones):
            for right_path, right_zone in hotzones[i + 1:]:
                if self.intersects(left_zone, right_zone):
                    self.warn(f"{path} hot zones overlap: {left_path} and {right_path}; static validation does not prove runtime z-order")

        missing = REQUIRED_BUTTONS - seen_inputs
        if missing:
            self.error(f"{path} is missing required inputs: {', '.join(sorted(missing))}")
        if touch_item is None:
            self.error(f"{path} is missing touch-screen item")
        elif lower is not None and self.valid_frame(touch_item.get("frame")) and self.valid_frame(lower.get("outputFrame")):
            if self.rect(touch_item["frame"]) != self.rect(lower["outputFrame"]):
                self.error(f"{path} touch frame must equal lower-screen outputFrame")

    def check_output_alpha(self, path: str, filename: str, view: dict[str, Any], upper: dict[str, Any] | None, lower: dict[str, Any] | None) -> None:
        image = self.read_image(filename)
        if image is None:
            return
        mapping = view.get("mappingSize")
        if not self.positive_pair(mapping, "width", "height"):
            image.close()
            return
        for label, screen in (("upper", upper), ("lower", lower)):
            if screen and screen.get("placement") == "app":
                continue
            output = screen.get("outputFrame") if screen else None
            if not self.valid_frame(output):
                continue
            x0 = max(0, int(output["x"] * image.width / mapping["width"]))
            y0 = max(0, int(output["y"] * image.height / mapping["height"]))
            x1 = min(image.width, int((output["x"] + output["width"]) * image.width / mapping["width"]))
            y1 = min(image.height, int((output["y"] + output["height"]) * image.height / mapping["height"]))
            if x1 <= x0 or y1 <= y0:
                continue
            alpha = image.crop((x0, y0, x1, y1)).getchannel("A")
            hist = alpha.histogram()
            total = sum(hist)
            if total and sum(hist[250:]) / total >= 0.98:
                self.warn(f"{path} {label} outputFrame region in {filename!r} is nearly fully opaque; game screen may be obscured")
        image.close()

    @staticmethod
    def positive_pair(obj: Any, x: str, y: str) -> bool:
        return isinstance(obj, dict) and isinstance(obj.get(x), (int, float)) and isinstance(obj.get(y), (int, float)) and obj[x] > 0 and obj[y] > 0

    @staticmethod
    def valid_frame(frame: Any) -> bool:
        return isinstance(frame, dict) and all(isinstance(frame.get(k), (int, float)) for k in ("x", "y", "width", "height")) and frame["width"] > 0 and frame["height"] > 0

    @staticmethod
    def inside(frame: dict[str, Any], canvas: tuple[float, float]) -> bool:
        return frame["x"] >= 0 and frame["y"] >= 0 and frame["x"] + frame["width"] <= canvas[0] and frame["y"] + frame["height"] <= canvas[1]

    def effective_edges(self, own: Any, inherited: Any, path: str) -> dict[str, float] | None:
        result: dict[str, float] = {}
        for key in ("top", "bottom", "left", "right"):
            value = inherited.get(key, 0) if isinstance(inherited, dict) else 0
            if isinstance(own, dict) and key in own:
                value = own[key]
            if not isinstance(value, (int, float)) or value < 0:
                self.error(f"{path}.extendedEdges.{key} must be a non-negative number")
                return None
            result[key] = value
        return result

    @staticmethod
    def rect(frame: dict[str, Any]) -> tuple[float, float, float, float]:
        return (frame["x"], frame["y"], frame["x"] + frame["width"], frame["y"] + frame["height"])

    @staticmethod
    def expand(rect: tuple[float, float, float, float], edges: dict[str, float]) -> tuple[float, float, float, float]:
        return (rect[0] - edges["left"], rect[1] - edges["top"], rect[2] + edges["right"], rect[3] + edges["bottom"])

    @staticmethod
    def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def report(self) -> int:
        for msg in self.errors:
            print(f"ERROR: {msg}")
        for msg in self.warnings:
            print(f"WARNING: {msg}")
        print(f"Summary: {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return 1 if self.errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Delta Emulator .deltaskin ZIP")
    parser.add_argument("deltaskin", help="path to .deltaskin ZIP archive")
    args = parser.parse_args(argv)
    return Validator(args.deltaskin).run()


if __name__ == "__main__":
    sys.exit(main())
