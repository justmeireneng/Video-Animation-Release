#!/usr/bin/env python3
"""
Scene Planner: Generates visual intent, metaphors, and camera lens specs for each scene.
"""
class ScenePlanner:
    def plan_scenes(self, script_scenes: list[dict]) -> list[dict]:
        planned = []
        for s in script_scenes:
            item = dict(s)
            item.setdefault("visual_intent", f"Visual storytelling for {s.get('title', '')}")
            item.setdefault("camera_lens", "50mm")
            planned.append(item)
        return planned
