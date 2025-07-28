# Adobe Hackathon Round 1B – Approach Explanation

## Problem Overview
The task for Round 1B is to act as an intelligent document analyst. Given a persona definition, a job-to-be-done, and a collection of documents (PDFs), the system must extract and prioritize the most relevant sections and subsections to support the persona’s objective.

---

## High-Level Architecture

The solution is modular and performs the following key steps:

1. **Document Parsing**:
   - For each PDF document, we extract a structured outline (title + headings) using logic built in Round 1A.
   - Text blocks are segmented and associated with headings to form logically coherent sections.

2. **Persona & Task Understanding**:
   - The persona is parsed either from a `.json` or `.txt` file.
   - The job-to-be-done is read as a text input.
   - This information defines the user’s intent and relevance context.

3. **Relevance Scoring**:
   - Each section’s content is compared against the persona's intent using:
     - **Keyword Overlap**: Matching tokens from persona focus areas and task description.
     - **Semantic Similarity** (if model is available): Using Sentence-BERT (`all-MiniLM-L6-v2`) to compute cosine similarity between the section and the persona+job query.
   - A combined score ranks the importance of each section.

4. **Sub-section Refinement**:
   - For the top-ranked sections, we extract the first few meaningful sentences to provide a concise preview or "refined snippet".

5. **Final Output**:
   - A structured JSON is generated containing:
     - Metadata (documents, persona, task, timestamp)
     - Ranked section list with titles, page numbers, and ranks
     - Subsection analysis with brief refined content

---

## Model Details

- **SentenceTransformer**: We use `all-MiniLM-L6-v2`, a compact BERT-based model optimized for semantic search. It's ~90MB and ideal for fast CPU inference.
- The model is cached locally inside `/app/models/` to support offline execution and reduce runtime.

---

## Offline & Docker Compatibility

- The solution does **not rely on any internet access**.
- All models and dependencies are either installed during Docker build or cached locally.
- The container processes each collection from `/app/input` and saves results to `/app/output`.

---

## Key Strengths

- Modular and extensible for future use.
- Handles multiple test cases automatically.
- Falls back to keyword-only scoring if the model is unavailable (e.g., in restricted environments).
- Compliant with execution time, model size (<1GB), and architecture constraints.

---

## Limitations

- Does not yet perform OCR for scanned PDFs.
- Assumes text-based PDFs and extractable structure.
- May miss relevance in documents with irregular formatting or unconventional headings.

---

## Conclusion

This solution intelligently surfaces key document insights based on user intent, making large PDFs more navigable and goal-oriented. It’s fast, extensible, and aligns well with the goals of Adobe’s “Connecting the Dots” challenge.

