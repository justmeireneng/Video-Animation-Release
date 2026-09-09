#!/usr/bin/env python3
"""
Storyboard Schema & Visual Guard for Whiteboard Animation.
Enforces semantic visual storytelling per scene, guards against repetitive templates,
and defines motion archetypes based on narration intent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 8 Motion Archetypes required by specification
MOTION_ARCHETYPES = [
    "sequential_draw",   # pipeline / process (A -> B -> C)
    "comparison_split",  # A vs B / before vs after / side-by-side
    "central_expand",    # central concept radiating outward
    "cause_effect",      # trigger -> reaction -> outcome
    "build_up",          # object constructed piece by piece
    "breakdown",         # system/role divided into sub-tasks/components
    "focus_shift",       # shifting attention between elements
    "punchline",         # hook or final takeaway emphasis
]

# Generic objects that must not repeat consecutively across scenes
GENERIC_OBJECTS = {"person", "laptop", "computer", "ai_box", "ai_icon", "arrow"}


class SimilarityViolationWarning(UserWarning):
    """Raised when consecutive scenes use repetitive visual templates."""
    pass


@dataclass
class SceneAnimationConfig:
    type: str = "sequential_draw"
    drawing_order: list[str] = field(default_factory=list)
    emphasis: list[str] = field(default_factory=list)
    hold_ms: int = 800

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "drawing_order": self.drawing_order,
            "emphasis": self.emphasis,
            "hold_ms": self.hold_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SceneAnimationConfig:
        if not data:
            return cls()
        return cls(
            type=data.get("type", "sequential_draw"),
            drawing_order=data.get("drawing_order", []),
            emphasis=data.get("emphasis", []),
            hold_ms=data.get("hold_ms", 800),
        )


@dataclass
class StoryboardScene:
    scene_id: str
    narration: str
    visual_intent: str
    visual_metaphor: str
    key_objects: list[str]
    composition: str
    what_changes_on_screen: str
    image_content: str = ""
    canvas_group_id: str | None = None
    animation: SceneAnimationConfig = field(default_factory=SceneAnimationConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "narration": self.narration,
            "visual_intent": self.visual_intent,
            "visual_metaphor": self.visual_metaphor,
            "key_objects": self.key_objects,
            "composition": self.composition,
            "what_changes_on_screen": self.what_changes_on_screen,
            "image_content": self.image_content,
            "canvas_group_id": self.canvas_group_id,
            "animation": self.animation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryboardScene:
        anim_data = data.get("animation")
        return cls(
            scene_id=data.get("scene_id", ""),
            narration=data.get("narration", ""),
            visual_intent=data.get("visual_intent", ""),
            visual_metaphor=data.get("visual_metaphor", ""),
            key_objects=data.get("key_objects", []),
            composition=data.get("composition", ""),
            what_changes_on_screen=data.get("what_changes_on_screen", ""),
            image_content=data.get("image_content", ""),
            canvas_group_id=data.get("canvas_group_id"),
            animation=SceneAnimationConfig.from_dict(anim_data if isinstance(anim_data, dict) else None),
        )


class VisualSimilarityGuard:
    """
    Validates storyboard scenes to ensure diversity of compositions,
    objects, and metaphors, preventing the repetitive 'person + laptop + AI' template.
    """

    @staticmethod
    def validate_storyboard(scenes: list[dict[str, Any] | StoryboardScene]) -> list[str]:
        parsed_scenes: list[StoryboardScene] = []
        for sc in scenes:
            if isinstance(sc, StoryboardScene):
                parsed_scenes.append(sc)
            else:
                parsed_scenes.append(StoryboardScene.from_dict(sc))

        warnings: list[str] = []

        for i in range(len(parsed_scenes)):
            sc = parsed_scenes[i]

            # 1. Validate motion archetype
            if sc.animation.type not in MOTION_ARCHETYPES:
                warnings.append(
                    f"[{sc.scene_id}] Motion archetype không hợp lệ: '{sc.animation.type}'. "
                    f"Hỗ trợ: {', '.join(MOTION_ARCHETYPES)}"
                )

            # 2. Check generic template repetition across 3 consecutive scenes
            if i >= 2:
                prev1 = parsed_scenes[i - 1]
                prev2 = parsed_scenes[i - 2]

                generic_set = set(GENERIC_OBJECTS)
                objs_current = set(o.lower().replace(" ", "_") for o in sc.key_objects)
                objs_prev1 = set(o.lower().replace(" ", "_") for o in prev1.key_objects)
                objs_prev2 = set(o.lower().replace(" ", "_") for o in prev2.key_objects)

                # Check if all 3 scenes primarily rely on generic objects
                if (
                    len(objs_current & generic_set) >= 2
                    and len(objs_prev1 & generic_set) >= 2
                    and len(objs_prev2 & generic_set) >= 2
                ):
                    warnings.append(
                        f"⚠️ Cảnh báo trùng lặp template: 3 scene liên tiếp ({prev2.scene_id}, "
                        f"{prev1.scene_id}, {sc.scene_id}) đều chứa cụm object chung chung "
                        f"(person + laptop/computer + ai_box). Cần đổi visual concept!"
                    )

                # Check identical composition in 3 consecutive scenes
                if (
                    sc.composition
                    and sc.composition == prev1.composition == prev2.composition
                ):
                    warnings.append(
                        f"⚠️ Cảnh báo lặp bố cục: 3 scene liên tiếp đều dùng bố cục '{sc.composition}'. "
                        f"Hãy đa dạng hóa góc nhìn (comparison, pipeline, breakdown, v.v.)."
                    )

        return warnings
