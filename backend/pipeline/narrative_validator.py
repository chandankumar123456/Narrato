def validate_narrative_arc(narrative_arc):
    for i in range(len(narrative_arc) - 1):
        current = narrative_arc[i]
        
        if current.get("cause") in ["", "derived", "basic", "from previous"]:
            raise Exception(f"Slide {i+1} weak cause")

        if current.get("next_trigger") in ["logical continuation", "next step"]:
            raise Exception(f"Slide {i+1} weak next_trigger")

        if not current.get("cause"):
            raise Exception(f"Slide {i+1} missing cause")

        if not current.get("next_trigger"):
            raise Exception(f"Slide {i+1} missing next_trigger")

        if i != 0 and i != len(narrative_arc)-1:
            if not current.get("tension"):
                raise Exception(f"Slide {i+1} missing tension")

    tension_count = sum(1 for s in narrative_arc if s.get("tension"))

    if tension_count < len(narrative_arc) // 2:
        raise Exception("Narrative too flat")

    # ✅ MOVE HERE
    roles = [s.get("role_in_story") for s in narrative_arc]

    if "Tension" not in roles:
        raise Exception("Narrative missing tension phase")

    if "Problem" not in roles:
        raise Exception("Narrative missing problem phase")

    return True