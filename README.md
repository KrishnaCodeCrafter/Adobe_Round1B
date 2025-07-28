# Adobe India Hackathon - Round 1B: Persona-Driven Document Intelligence

## Challenge Overview

This project provides a solution for Round 1B of the Adobe India Hackathon, "Connecting the Dots." The core challenge is to build an intelligent document analysis system capable of extracting and prioritizing the most relevant sections from a collection of PDF documents. This analysis is driven by a specified user **persona** and their particular **job-to-be-done**.

This solution leverages the document outlining capabilities developed in Round 1A and extends them with advanced text analysis and semantic understanding to deliver contextually relevant insights.

## Features

* **Multi-Document Processing:** Handles a collection of 3-10 related PDF documents.

* **Persona-Driven Analysis:** Integrates a persona definition (role, expertise, focus areas) and a specific job description to guide information extraction.

* **Intelligent Section Extraction:** Utilizes hierarchical PDF outline (from Round 1A) to accurately segment documents into logical sections.

* **Relevance Scoring & Ranking:** Scores document sections based on their semantic and keyword-based relevance to the provided persona and job-to-be-done. Sections are then ranked by importance.

* **Sub-Section Analysis:** Provides refined, concise text snippets from the most relevant sections, offering granular insights.

* **JSON Output:** Generates structured JSON output conforming to the challenge's specified format (`challenge1b_output.json`).

* **Dockerized Solution:** Packaged in a Docker container for consistent, isolated, and offline execution, meeting all hackathon environment requirements.

## 🚀 Getting Started

These instructions will get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Docker Desktop installed and running on your Windows, macOS, or Linux machine.

* Git (optional, but recommended for cloning this repository).

### Installation and Execution

1.  **Clone the repository (or set up the directory manually):**

    ```bash
    git clone [https://github.com/KrishnaCodeCrafter/Adobe_Round1B.git](https://github.com/KrishnaCodeCrafter/Adobe_Round1B.git)
    cd Adobe_Round1B
    ```

    *(If you're not using Git, manually create the directory structure and place the files.)*

2.  **Place Sample Input Files:**
    Create subdirectories within the `input/` folder for your test cases (e.g., `input/test_case_1/`). Inside each test case folder, create a `documents/` folder and place your PDF files there. Also, create `persona_definition.json` (or `.txt`) and `job_to_be_done.txt` for each test case as per the structure above.

3.  **Build the Docker Image:**
    This step will download necessary dependencies and the pre-trained NLP model (`all-MiniLM-L6-v2`) and bundle everything into a Docker image. This process requires an active internet connection.

    ```bash
    docker build --platform linux/amd64 -t myr1bsolution:latest .
    ```

    *(This command will take some time, especially on the first run, as it downloads the Python base image and the NLP model.)*

4.  **Run the Docker Container:**
    Once the image is built, execute the following command. This will run your solution, process all test cases found in the `input/` directory, and save the results to the `output/` directory. The container will run in an isolated environment without internet access.

    * **For PowerShell:**

        ```bash
        docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" --network none myr1bsolution:latest
        ```

    * **For Command Prompt (CMD):**

        ```cmd
        docker run --rm -v "%cd%\input:/app/input" -v "%cd%\output:/app/output" --network none myr1bsolution:latest
        ```

5.  **Check Results:**
    After the command finishes, your processed JSON output files will be available in the `output/` directory of your local `Adobe_Round1B` folder. Each test case will have its own JSON file (e.g., `test_case_1_academic_research_output.json`).

## Methodology & Approach

This solution for Round 1B builds modularly on the document parsing foundation established in Round 1A.

1.  **Document Sectioning (Leveraging Round 1A):**

    * The `pdf_parser.py` module, containing the core logic from Round 1A, is used to extract the hierarchical outline (Title, H1, H2, H3) from each PDF.

    * The `extract_document_sections` function in `main_round1b.py` then takes this outline and performs a detailed block-level text extraction using `PyMuPDF (fitz)`. It intelligently segments the document's full text content, associating each paragraph or block of text with its most relevant preceding heading based on their vertical positions. This ensures coherent sections for analysis.

2.  **Input Parsing:**

    * The `load_persona_and_job` function dynamically reads the `persona_definition.json` (or `.txt`) and `job_to_be_done.txt` files for each individual test case, making the solution flexible for diverse inputs.

3.  **Relevance Scoring:**

    * This is the core "intelligence" of Round 1B. For each extracted document section, a relevance score is calculated based on two primary mechanisms:

        * **Enhanced Keyword Matching:** Keywords derived from the `job_to_be_done` and the persona's `focus_areas` are extracted. Sections containing these keywords receive a base score.

        * **Semantic Similarity (NLP-powered):** A pre-trained `SentenceTransformer` model, `all-MiniLM-L6-v2`, is utilized. A combined query embedding is generated from the persona's description, role, and the job-to-be-done. This query is then compared (using cosine similarity) against the embedding of each document section's text. This provides a more nuanced understanding of conceptual relevance beyond exact keyword matches. The semantic similarity score is heavily weighted.

4.  **Section Ranking:**

    * All processed sections, each with its calculated relevance score, are sorted in descending order. A final 1-based `importance_rank` is then assigned based on this sorted order, indicating the most pertinent sections.

5.  **Sub-Section Analysis:**

    * For the top N (currently 10) most relevant sections, a granular `refined_text` is extracted. For simplicity and to adhere to constraints, this currently involves extracting the first few sentences of the relevant section. In a more advanced scenario, this could involve extractive summarization or more targeted information extraction.

## Constraints Adherence

This solution is designed to strictly adhere to the challenge constraints:

* **CPU Only:** All processing is done on the CPU; no GPU dependencies are used.

* **Model Size (**$\\le 1$**GB):** The `all-MiniLM-L6-v2` Sentence Transformer model is approximately 90MB, well within the 1GB limit.

* **Processing Time (**$\\le 60$ **seconds for 3-5 documents):** The use of efficient PDF parsing libraries (`PyMuPDF`) and a relatively small NLP model helps keep processing times optimized.

* **Offline Execution:** The `SentenceTransformer` model is pre-downloaded and saved into the Docker image during the build process. The `docker run` command uses `--network none`, ensuring no external network calls are made during execution.

## Potential Future Improvements

* **More Advanced Sub-Section Analysis:** Implement extractive summarization techniques (e.g., TextRank, or fine-tuned smaller models) or targeted information extraction based on question-answering for `refined_text`.

* **Persona Nuance:** Develop more sophisticated ways to parse and utilize persona details, such as dynamically weighting different relevance factors based on the persona's role (e.g., "Investment Analyst" might prioritize numerical data).

* **Hierarchical Ranking Refinement:** Further refine the ranking by considering the hierarchical position of sections (e.g., H1 sections might have a base importance boost).

* **Error Handling and Robustness:** Enhance parsing for highly complex or scanned PDFs, potentially integrating light-weight OCR if within limits.
