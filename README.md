Narrato is a **design-first, state-driven AI system** that generates structured, visually appealing presentations from natural language prompts.

It is inspired by modern tools like Gamma, Chronicle, and Moda, focusing on:
- Story-driven generation
- Design-aware slide creation
- Dynamic constraint handling

---

# 1. Core Philosophy

Narrato is NOT:
> prompt → text → slides

Narrato IS:
> prompt → structured state → story → slide plan → design-aware slides → presentation

---

# 2. System Architecture Overview


Frontend (User Input)
↓
API Layer (FastAPI)
↓
Orchestrator (Controller / Agent)
↓
Core Pipeline:

Prompt Understanding
State Builder
Story Generation
Slide Planning
Slide Typing
Content Structuring
Visual Mapping
Design Mapping
PPT Generation
↓
Download Response

---

# 3. Core Pipeline (Detailed)

## 3.1 Prompt Understanding Layer

### Input:
Natural language prompt

### Output:
Extracted constraints

### Responsibilities:
- Detect:
  - slide_count
  - sections
  - examples_count
  - tone
  - presentation_type
  - image requirements
- Handle:
  - vague prompts
  - partial constraints
  - strict instructions

---

## 3.2 State Layer (Single Source of Truth)

### Concept:
All downstream components depend ONLY on this structured state.

### Rules:
- user input > AI inference > default values
- partial fields allowed

### Example:


PresentationState:
topic: str
presentation_type: str
slide_count: int
sections: list[str]
tone: str
audience: str
examples_count: int
image_preference: bool
visual_style: str


---

## 3.3 Story Generation Layer (Critical)

### Purpose:
Convert topic into a logical narrative

### Output:


Story:
narrative_type
key_message
sections_flow:
- intro
- problem
- solution
- market
- conclusion


### Importance:
This ensures:
- logical flow
- better storytelling
- non-random slide ordering

---

## 3.4 Slide Planning Layer

### Purpose:
Convert story into slide-level structure

### Output:


SlidePlan:
total_slides: int
slides:
- slide_id
- section
- purpose


---

## 3.5 Slide Type System (Design Backbone)

### Concept:
Each slide is assigned a predefined type

### Example Types:


SlideType:

title
section_header
problem
stats
features
comparison
timeline
conclusion

### Each type defines:
- layout structure
- content schema

---

## 3.6 Content Structuring Layer

### Purpose:
Generate structured content instead of raw text

### Example:


ProblemSlide:
title: str
points: list[str]
stat: str


### Rule:
No paragraphs — only structured data

---

## 3.7 Visual Mapping Layer

### Purpose:
Generate context-aware visuals

### Output:


image_query: str


### Example:
- "food supply chain diagram"
- "AI learning classroom illustration"

---

## 3.8 Design Mapping Layer

### Concept:
Separate content from design


SlideType → Layout Template → Content Injection


### Example:

problem_slide → 3-card layout → fill points
stats_slide → big number layout → fill stat


---

## 3.9 PPT Generation Layer

### Responsibilities:
- Create slides
- Apply layouts
- Insert content
- Add images
- Maintain spacing and readability

---

# 4. Orchestrator (Controller Layer)

### Role:
Controls full pipeline execution

### Responsibilities:


parse_prompt()
build_state()
generate_story()
plan_slides()
assign_slide_types()
generate_content()
map_visuals()
apply_design()
generate_ppt()


---

# 5. Backend Architecture

## Framework:
- FastAPI

## Endpoints:


POST /generate
input: prompt
output: ppt file

GET /download/{id} (optional)

GET /status (optional)


---

# 6. Frontend Architecture

## Components:
- Prompt input field
- Optional controls:
  - slide count
  - style
- Generate button
- Loading state
- Download button

## Responsibility:
- Collect input
- Send request
- Display progress
- Enable download

---

# 7. Dynamic Behavior Model

## Priority Logic:


Final Value =
user_input OR inferred_value OR default


---

## Modes:

### 1. Vague Input
System decides everything

### 2. Partial Input
Hybrid behavior

### 3. Strict Input
System obeys fully

---

# 8. Design Principles

## 1. Story First
Slides follow narrative, not random generation

## 2. Structured Content
No raw paragraphs

## 3. Design Consistency
Same style across slides

## 4. Separation of Concerns
- content ≠ design
- story ≠ slides

## 5. Deterministic Execution
All generation depends on final state

---

# 9. Minimum Viable Product (MVP)

Must include:
- prompt input
- state extraction
- slide planning
- structured content generation
- PPT creation
- download functionality

---

# 10. Advanced Features (Optional)

- multiple design themes
- real-time preview
- editing before download
- animation support
- export formats (PDF, Google Slides)

---

# 11. Summary

Narrato is:

> A dynamic, state-driven, storytelling-based AI system that generates visually structured presentations from natural language input.

### Core Pipeline:


Prompt
→ State
→ Story
→ Slide Plan
→ Slide Types
→ Structured Content
→ Visual Mapping
→ Design Templates
→ PPT


---