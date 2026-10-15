# SPDX-License-Identifier: Elastic-2.0
# Copyright (c) 2026 ClaymoreLab
"""Shared stick-figure rules for character, storyboard and video prompts."""

from dataclasses import dataclass

THEMES = ("classic", "modern", "prehistoric", "1a", "1b", "2a", "2b", "3")
RULES_VERSION = "stickman-themes-v2"
THEME_ALIASES = {"classic": "1a", "modern": "2b", "prehistoric": "3"}


def canonical_theme(theme: str | None) -> str:
    value = THEME_ALIASES.get(theme, theme) if theme else "1a"
    if value not in {"1a", "1b", "2a", "2b", "3"}:
        raise ValueError(f"Unsupported stickman theme: {theme}")
    return value

IDENTITY_RULE = (
    "STICK-FIGURE IDENTITY: Keep each character's hollow circular head, line weight, "
    "relative height, simple hair silhouette and identifying accessories consistent. "
    "Use connected single-line torsos and limbs. Translate age, identity and costume "
    "cues into simple outlines; do not reproduce realistic faces or body volumes. "
    "Preserve the story's characters, actions, necessary props and locations. "
    "If the reference is a photograph or ordinary animation, use it for identity cues "
    "and redraw those cues as a stick figure. If it is already a stick figure, preserve "
    "its graphic design. Simple line expressions are allowed when the action needs them."
)

RENDER_RULE = (
    "STICK-FIGURE RENDERING: Flat pure white canvas, clean black medium-weight lines, "
    "hollow circular heads and single-line bodies. Keep simplified stick-figure "
    "proportions; never convert them into natural human anatomy. No realistic skin, "
    "detailed facial features, 3D volume, cinematic shading, gradients or paper texture. "
    "Draw required scenery and objects as sparse readable black outlines on white. "
    "Use monochrome by default; retain only explicitly requested accent colors. "
    "Internal fluorescent identity markers are not final visible colors. "
    "Keep character count, crop, camera angle, spatial layout, pose and prop placement. "
    "Reference images never override the storyboard's geometry. Material-only scene "
    "references supply semantic appearance cues only, never layout or camera. "
    "Each figure has two arms and two legs, allowing natural occlusion; each limb "
    "has only its current pose, without duplicate limbs or lingering limb trails. "
    "No added captions, labels, watermarks or visible writing."
)

VIDEO_RULE = (
    "STICK-FIGURE VIDEO STYLE: Maintain flat white backgrounds and clean black line "
    "animation throughout the shot. Preserve the reference's hollow head shape, "
    "line weight, single-line body, relative character sizes and key accessories. "
    "Keep requested actions and necessary scene objects readable. Each moving limb "
    "replaces its previous pose; do not add extra arms, legs or limb trails. "
    "Allow natural occlusion. Avoid realistic human anatomy, skin detail, 3D volume, "
    "style drift, flickering lines and generated captions. Keep only explicitly "
    "requested accent colors."
)


@dataclass(frozen=True)
class ThemeRules:
    identity: str
    render: str
    video: str
    avoid: str
    tag: str


def theme_rules(theme: str | None = None) -> ThemeRules:
    theme = canonical_theme(theme)
    common = (
        "Preserve the story's cast, actions, essential props and explicit location. "
        "Keep character count, crop, camera angle, geometry, poses and prop placement. "
        "Reference sheets provide identity cues, never their page layout or camera. "
        "Internal marker colors identify characters only and are not final artwork colors. "
        "Each limb has only its current pose; allow natural occlusion without extra limbs. "
        "No generated writing, subtitles, watermarks or speech bubbles."
    )
    if theme == "1a":
        return ThemeRules(IDENTITY_RULE, RENDER_RULE, VIDEO_RULE,
                          "No realistic skin, volumetric human bodies, gradients, cinematic shading or paper texture.",
                          "MINIMAL 2D STICK FIGURE, BLACK LINE ON WHITE")
    if theme == "1b":
        identity = IDENTITY_RULE.replace("STICK-FIGURE IDENTITY", "DARK STICK-FIGURE IDENTITY")
        render = RENDER_RULE.replace("Flat pure white canvas, clean black", "Flat pitch-black canvas, clean white")
        render = render.replace("black outlines on white", "white outlines on black")
        video = VIDEO_RULE.replace("flat white backgrounds and clean black", "flat pitch-black backgrounds and clean white")
        return ThemeRules(identity, render, video,
                          "No white background, realistic skin, 3D bodies, gradients, cinematic shading or paper texture.",
                          "MINIMAL 2D STICK FIGURE, WHITE LINE ON BLACK")
    if theme in {"2a", "2b"}:
        identity = (
            "MODERN STICK-FIGURE IDENTITY: Use white filled round heads, simple dot eyes "
            "and line expressions, black stick limbs and simplified graphic clothing. "
            "A smooth red beanie without a pom-pom and a yellow shirt are the default "
            "lead-character outfit only when no outfit is specified. Do not dress the "
            "whole cast identically. Preserve each role's distinguishing accessories, "
            "relative size and approved character design across shots."
        )
        render = (
            "MODERN CINEMATIC STICK-FIGURE RENDERING: Crisp clean 2D character linework "
            "in full-color story environments with cinematic light and readable depth. "
            "Keep the characters visibly simple and two-dimensional; do not inflate "
            "their line limbs into realistic human bodies. Use the specified location; "
            "do not replace it with a generic studio or add technology UI unrequested. "
        )
        tag = "COLORFUL 2D STICK FIGURE, CINEMATIC STORY"
        avoid = "No realistic human skin or detailed eyes, 3D human bodies, extra limbs or identity drift."
        if theme == "2a":
            render = (
                "MODERN STUDIO TECH STICK-FIGURE RENDERING: Simple 2D characters in a "
                "bright white high-key studio, subtle light-gray perspective floor grid, "
                "floating cyan and electric blue translucent glass UI and clean negative space. "
                "Express the story's necessary objects as sparse readable props and icon-only "
                "graphics within this studio treatment. Keep characters two-dimensional. "
                "No written interface copy. "
            )
            tag = "2D STICK FIGURE, WHITE STUDIO, CYAN GLASS UI"
            avoid += " No circuit-board textures, sci-fi wall panels, spaceship corridors, cracked concrete or grunge."
    else:
        identity = (
            "PREHISTORIC HAND-DRAWN IDENTITY: White filled round or oval cartoon heads, "
            "expressive simple faces and brows, black stick limbs, rough hand-drawn "
            "outlines and simplified clothing. Cast distinct characters suited to the "
            "story and lock each character's head shape, hair silhouette, relative "
            "height and costume across shots. Animal-hide clothing is a default only "
            "when wardrobe is unspecified; preserve explicit character descriptions."
        )
        render = (
            "PREHISTORIC HAND-DRAWN RENDERING: Earthy ochre, sand, brown and muted green "
            "palette, warm fire accents, subtle paper texture and imperfect bold "
            "hand-drawn lines. Use sparse cartoon settings. Caves and wilderness are "
            "defaults only when location is unspecified; preserve explicit scenes and "
            "necessary objects. Express the existing dramatic or comic actions visually; "
            "do not rewrite dialogue, history, genre or story ending. "
        )
        tag = "HAND-DRAWN STICK FIGURE, EARTHY PALETTE"
        avoid = "No realistic human rendering, photorealistic skin, polished 3D CGI or duplicate limbs."
    render += common
    video = f"STICK-FIGURE VIDEO STYLE ({theme}): {identity} {render} Keep motion smooth and line weight stable. {avoid}"
    return ThemeRules(identity, render, video, avoid, tag)


def append_video_style(prompt: str, representation: str, theme: str | None = None) -> str:
    """Apply a resolved style once, without changing ordinary video requests."""
    if representation != "stick_figure":
        return prompt
    rule = theme_rules(theme).video
    if rule in prompt:
        return prompt
    return f"{prompt.rstrip()}\n\n{rule}".strip()


def character_reference_prompt(
    *, character_name: str, character_tag: str, description: str,
    style: str, avoid: str, layout: str, has_costume_reference: bool = False,
    theme: str | None = None,
) -> str:
    """Keep the existing portrait/sheet contract while replacing facial fidelity."""
    costume = (
        "Use the costume reference only for simplified outfit and accessory cues."
        if has_costume_reference else ""
    )
    rules = theme_rules(theme)
    return f"""Create a stick-figure production character reference.
CHARACTER: {character_tag} ({character_name})
LAYOUT: {layout}
CHARACTER DESCRIPTION: {description}
{rules.identity}
{rules.render}
{costume}
STYLE: {style}
AVOID: {avoid}
Show only this character, with a consistent design across all views.
For this identity-reference layout, use a neutral backdrop without narrative scenery.
No printed tags, labels or panel numbers.""".strip()
