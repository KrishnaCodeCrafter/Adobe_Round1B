import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import numpy as np # For numerical operations with embeddings
import fitz 

from pdf_parser import extract_outline_from_pdf, extract_title_from_pdf

try:
    from sentence_transformers import SentenceTransformer, util
    
    MODEL_NAME = 'all-MiniLM-L6-v2'
    MODEL_PATH_IN_CONTAINER = Path("/app/models") / MODEL_NAME

    semantic_model = None # Initialize to None

    if MODEL_PATH_IN_CONTAINER.exists():
        semantic_model = SentenceTransformer(str(MODEL_PATH_IN_CONTAINER))
        print(f"Loaded SentenceTransformer model from {MODEL_PATH_IN_CONTAINER}")
    else:
        print(f"Warning: SentenceTransformer model not found at {MODEL_PATH_IN_CONTAINER}.")
        print(f"Attempting to download '{MODEL_NAME}'. This will fail if no internet during runtime.")
        try:
            semantic_model = SentenceTransformer(MODEL_NAME)
            semantic_model.save_pretrained(MODEL_PATH_IN_CONTAINER)
            print(f"Downloaded and loaded SentenceTransformer model '{MODEL_NAME}'.")
        except Exception as dl_e:
            print(f"Error during model download: {dl_e}. Semantic similarity will be disabled.")

except ImportError:
    print("Error: 'sentence-transformers' not found. Please install it (`pip install sentence-transformers`).")
    print("Falling back to keyword-only relevance scoring.")
    semantic_model = None
except Exception as e:
    print(f"Generic error during SentenceTransformer setup: {e}. Falling back to keyword-only relevance scoring.")
    semantic_model = None

# --- End Sentence Transformers Setup ---


# ---------------------- Document Sectioning ----------------------
def extract_document_sections(pdf_path: Path) -> List[Dict]:
    """
    Extracts text content from a PDF and associates it with the nearest preceding heading.
    Leverages the outline from Round 1A to segment the document logically.
    Returns a list of dictionaries, each representing a distinct section with its content.
    """
    doc_sections = []
    
    outline = extract_outline_from_pdf(pdf_path)

    doc = fitz.open(pdf_path)
    
    all_content_blocks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict") # Get detailed text layout
        for block in text_dict.get("blocks", []):
            if block["type"] == 0:  # Only process text blocks (type 0)
                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span["text"]
                
                if block_text.strip(): # Add non-empty blocks
                    all_content_blocks.append({
                        "text": block_text.strip(),
                        "page": page_num + 1,  # Store as 1-indexed page number
                        "y0": block["bbox"][1], # Top Y-coordinate of the block
                        "x0": block["bbox"][0] # Left X-coordinate for potential indentation checks
                    })
    
    all_content_blocks.sort(key=lambda x: (x["page"], x["y0"]))

    heading_markers = []
    for h in outline:
        found_heading_block = None
        for block in all_content_blocks:
            if block["page"] == h["page"] and h["text"] in block["text"]:
                found_heading_block = block
                break
        
        if found_heading_block:
            heading_markers.append({
                "type": "heading_marker",
                "text": h["text"],
                "level": h["level"],
                "page": h["page"],
                "y0": found_heading_block["y0"]
            })
        else:
            heading_markers.append({
                "type": "heading_marker",
                "text": h["text"],
                "level": h["level"],
                "page": h["page"],
                "y0": 0 
            })

    combined_stream = sorted(all_content_blocks + heading_markers, key=lambda x: (x["page"], x["y0"]))

    current_section_title = "Document Start"
    current_section_level = "H0"
    current_section_text_parts = []
    current_section_start_page = 1 

    for item in combined_stream:
        if item.get("type") == "heading_marker":
            if current_section_text_parts: 
                doc_sections.append({
                    "document": pdf_path.name,
                    "page_number": current_section_start_page,
                    "section_title": current_section_title,
                    "section_text": "\n".join(current_section_text_parts),
                    "level": current_section_level
                })
            
            current_section_title = item["text"]
            current_section_level = item["level"]
            current_section_start_page = item["page"]
            current_section_text_parts = [] 
        else:
            current_section_text_parts.append(item["text"])
            
    if current_section_text_parts:
        doc_sections.append({
            "document": pdf_path.name,
            "page_number": current_section_start_page,
            "section_title": current_section_title,
            "section_text": "\n".join(current_section_text_parts),
            "level": current_section_level
        })

    doc.close()
    return doc_sections

# ---------------------- Persona & Job-to-be-Done Processing ----------------------

def load_persona_and_job(input_case_dir: Path) -> Dict[str, Any]:
    """
    Loads persona definition (from JSON or TXT) and job-to-be-done from input files
    within a specific test case directory.
    """
    persona = {}
    job_to_be_done = ""

    persona_path_json = input_case_dir / "persona_definition.json"
    persona_path_txt = input_case_dir / "persona_definition.txt"

    if persona_path_json.exists():
        with open(persona_path_json, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        print(f"  Loaded persona from {persona_path_json.name}")
    elif persona_path_txt.exists():
        with open(persona_path_txt, 'r', encoding='utf-8') as f:
            persona_desc = f.read().strip()
            persona = {"description": persona_desc, "role": "Unspecified Role", "focus_areas": ""}
        print(f"  Loaded persona from {persona_path_txt.name} (as text description)")
    else:
        raise FileNotFoundError(f"Neither persona_definition.json nor persona_definition.txt found in {input_case_dir}")

    job_path = input_case_dir / "job_to_be_done.txt"
    if job_path.exists():
        with open(job_path, 'r', encoding='utf-8') as f:
            job_to_be_done = f.read().strip()
        print(f"  Loaded job-to-be-done from {job_path.name}")
    else:
        raise FileNotFoundError(f"job_to_be_done.txt not found in {input_case_dir}")

    return {"persona": persona, "job_to_be_done": job_to_be_done}


# ---------------------- Relevance Scoring ----------------------

def calculate_relevance(text: str, persona_info: Dict, job_text: str, nlp_model: Any = None) -> float:
    """
    Calculates a relevance score for a given text section based on persona and job.
    Combines keyword matching and semantic similarity (if NLP model is available).
    """
    score = 0.0

    all_keywords = set()
    job_keywords_raw = re.findall(r'\b\w+\b', job_text.lower())
    all_keywords.update(job_keywords_raw)

    if persona_info.get("focus_areas"):
        persona_focus_keywords_raw = re.findall(r'\b\w+\b', persona_info["focus_areas"].lower())
        all_keywords.update(persona_focus_keywords_raw)
    
    text_tokens_lower = re.findall(r'\b\w+\b', text.lower())
    
    for kw in all_keywords:
        if kw in text_tokens_lower:
            score += 2.0

    if nlp_model:
        try:
            query_parts = [job_text]
            if persona_info.get("description"):
                query_parts.append(f"Persona description: {persona_info['description']}")
            if persona_info.get("role"):
                query_parts.append(f"Role: {persona_info['role']}")
            if persona_info.get("focus_areas"):
                query_parts.append(f"Focus areas: {persona_info['focus_areas']}")
            
            combined_query = ". ".join(query_parts)
            
            query_embedding = nlp_model.encode(combined_query, convert_to_tensor=True)
            text_embedding = nlp_model.encode(text, convert_to_tensor=True)
            
            cosine_score = util.pytorch_cos_sim(query_embedding, text_embedding).item()
            normalized_cosine = (cosine_score + 1) / 2
            score += normalized_cosine * 10.0
        except Exception as e:
            print(f"Semantic similarity failed for a section. Error: {e}")
            pass 

    # Add minor bonus for very short sections that match keywords (potential titles/subheadings)
    if len(text.split()) < 10 and any(kw in text.lower() for kw in all_keywords):
        score += 1.0

    return score

# ---------------------- Main Round 1B Processor ----------------------

def process_single_test_case(input_case_dir: Path, output_dir: Path):
    """
    Processes a single test case directory, extracts sections, ranks them,
    and generates the output JSON.
    """
    case_name = input_case_dir.name
    print(f"\n--- Processing Test Case: {case_name} ---")

    try:
        persona_job_data = load_persona_and_job(input_case_dir)
        persona_info = persona_job_data["persona"]
        job_to_be_done = persona_job_data["job_to_be_done"]
    except FileNotFoundError as e:
        print(f"  Skipping test case {case_name} due to missing input file: {e}")
        return
    except Exception as e:
        print(f"  Skipping test case {case_name} due to error loading persona/job data: {e}")
        return

    documents_dir = input_case_dir / "documents"
    pdf_files = list(documents_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"  No PDF files found in {documents_dir}. Skipping test case {case_name}.")
        return

    all_extracted_sections = []
    input_document_names = [f.name for f in pdf_files]

    print("  Starting section extraction from documents...")
    for pdf_file in pdf_files:
        print(f"    Processing document: {pdf_file.name}")
        sections = extract_document_sections(pdf_file)
        all_extracted_sections.extend(sections)
    print(f"  Extracted {len(all_extracted_sections)} potential sections for {case_name}.")

    # 3. Score and Rank Sections
    print("  Calculating relevance and ranking sections...")
    ranked_sections = []
    if not all_extracted_sections:
        print(f"  No sections extracted to rank for {case_name}.")
    
    for section in all_extracted_sections:
        relevance_score = calculate_relevance(
            section["section_text"],
            persona_info,
            job_to_be_done,
            nlp_model=semantic_model
        )
        ranked_sections.append({
            "document": section["document"],
            "page_number": section["page_number"],
            "section_title": section["section_title"],
            "importance_rank": relevance_score, 
            "section_text_raw": section["section_text"] 
        })

    ranked_sections.sort(key=lambda x: x["importance_rank"], reverse=True)

    final_extracted_sections_output = []
    for i, section in enumerate(ranked_sections):
        final_extracted_sections_output.append({
            "document": section["document"],
            "page_number": section["page_number"],
            "section_title": section["section_title"],
            "importance_rank": i + 1 
        })

    print("  Performing sub-section analysis on top relevant sections...")
    sub_section_analysis_results = []
    num_sections_for_analysis = min(10, len(ranked_sections)) 
    
    for i in range(num_sections_for_analysis):
        section = ranked_sections[i]
        full_text = section["section_text_raw"]
        
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        refined_text = " ".join(sentences[:min(3, len(sentences))])

        if refined_text:
            sub_section_analysis_results.append({
                "document": section["document"],
                "page_number": section["page_number"],
                "refined_text": refined_text
            })

    output_data = {
        "metadata": {
            "input_documents": input_document_names,
            "persona": persona_info,
            "job_to_be_done": job_to_be_done,
            "processing_timestamp": datetime.now().isoformat()
        },
        "extracted_sections": final_extracted_sections_output,
        "sub_section_analysis": sub_section_analysis_results
    }

    # Save the output for this specific test case
    output_file_name = f"{case_name}_output.json"
    output_file_path = output_dir / output_file_name
    try:
        with open(output_file_path, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"  Test Case '{case_name}' complete. Output saved to {output_file_path.name}")
    except Exception as e:
        print(f"  Error saving output JSON for {case_name} to {output_file_path.name}: {e}")

# ---------------------- Main Entry Point ----------------------
if __name__ == "__main__":
    print("--- Starting Round 1B: Persona-Driven Document Intelligence (Multiple Test Cases) ---")
    
    Path("/app/models").mkdir(parents=True, exist_ok=True) 

    base_input_root = Path("/app/input")
    base_output_root = Path("/app/output")
    base_output_root.mkdir(parents=True, exist_ok=True)

    test_case_dirs = []
    for entry in base_input_root.iterdir():
        if entry.is_dir() and (entry / "documents").is_dir():
            test_case_dirs.append(entry)
    
    if not test_case_dirs:
        print(f"No test case directories found in {base_input_root}. Please structure inputs as: input/test_case_name/documents/...")
    else:
        for tc_dir in test_case_dirs:
            process_single_test_case(tc_dir, base_output_root)

    print("--- Finished processing all available test cases ---")

