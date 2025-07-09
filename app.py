from flask import Flask, request, jsonify
import pandas as pd
from sentence_transformers import SentenceTransformer
from numpy import dot
from numpy.linalg import norm
import heapq
from flask_cors import CORS
from collections import defaultdict
import re
import requests
import time
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, Filter
from deep_translator import GoogleTranslator
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import json
from dotenv import load_dotenv
import os

load_dotenv()
qdrant_api_key = os.getenv("qdrant_api_key")
gemini_api_key = os.getenv("gemini_api_key")
# --- Embedding Model ---
class BGEEmbedder:
    def __init__(self, model_name="BAAI/bge-m3"):
        self.model = SentenceTransformer(model_name)
        self.prefix = "Represent this sentence for searching relevant passages: "
    def embed(self, texts, batch_size=16):
        texts_with_prefix = [
            text if text.startswith(self.prefix) else self.prefix + text
            for text in texts
        ]
        embeddings = self.model.encode(
            texts_with_prefix,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings

# --- Qdrant client ---
client = QdrantClient(
    url=r"https://0f47d391-b7c1-45d9-a956-5f7228cd80f3.europe-west3-0.gcp.cloud.qdrant.io:6333",
    api_key=qdrant_api_key,
    prefer_grpc=False
)

# --- Load subject map and embeddings ---
DF_PATH = r"D:\Learn\Semester_5\SEG301\Fap-Chat\data\DATA cố định\FLM\FINAL\FINAL_DF_FLM.csv"
df_flm = pd.read_csv(DF_PATH)
subject_map = {
    row["SubjectCode"]: f"{row['SubjectCode']} - {row['Subject Name']}"
    for _, row in df_flm[["SubjectCode", "Subject Name"]].dropna().drop_duplicates().iterrows()
}
def filter_subjects(subject_map):
    for prefix in ["PHE_COM", "AI17_COM", "AI17_GRA_ELE"]:
        subject_map = {k: v for k, v in subject_map.items() if not k.startswith(prefix)}
    return subject_map
subject_map = filter_subjects(subject_map)

embedder = BGEEmbedder()
subject_embeddings = {
    code: embedder.embed([name])[0]
    for code, name in subject_map.items()
}

def detect_subject(query, top_k=2, threshold=0.7):
    query_vec = embedder.embed([query])[0]
    sims = {
        code: dot(query_vec, emb) / (norm(query_vec) * norm(emb))
        for code, emb in subject_embeddings.items()
    }
    top_subjects = heapq.nlargest(top_k, sims.items(), key=lambda x: x[1])
    top_subjects = [(code, score) for code, score in top_subjects if score >= threshold]
    return top_subjects

# --- Type map, type embedding, detect type ---
TYPE_DESCRIPTIONS = {
    "overview": "queries about which subjects match certain characteristics (e.g., taught in a specific semester, related to a topic, or having certain prerequisites), or general overviews of subject goals, credits, syllabus, or curriculum structure.",
    "construtive_question": "thought-provoking questions",
    "assessment": "evaluations, types of tests, exams, FE, PE, TE and grading weights",
    "session": "lecture sessions, lessons, topics covered in each week or session",
    "material": "recommended textbooks, reference materials, slides, or other learning resources",
    "learning outcome": "learning outcome, expected knowledge, skills, or competencies students should achieve after completing the course",
    "student_list": "list of students enrolled in the course, including name, student ID, and email",
    "guide": "instructions or guidance for students on how to complete tasks, assignments, projects, or use certain tools/platforms."
}
TYPE_KEYWORDS = {
    "overview": ["overview", "objective", "goal", "credits", "semester", "prerequisite", "syllabus", 'subject', 'subjects'],
    "construtive_question": ["why", "how", "what if", "critical", "discussion", "reflect", "ethical"],
    "assessment": ["exam", "test", "quiz", "grading", "project", "evaluation", "score"],
    "session": ["week", "lesson", "lecture", "topic", "schedule", "session", "class"],
    "material": ["textbook", "slide", "document", "reading", "reference", "material", "resource"],
    "learning outcome": ["learn", "outcome", "skill", "competency", "ability", "achieve", "knowledge"],
    "student_list": ["student", "name", "id", "mssv", "email", "class list", "enrolled", "danh sách sinh viên"],
    "guide": ["how to", "instruction", "guide", "tutorial", "step", "steps", "do", "complete", "submit", "platform", "tool", "usage", "usage guide", "help", "assist", "support", "direction"]
}
type_embeddings = {
    t: embedder.embed([desc])[0] for t, desc in TYPE_DESCRIPTIONS.items()
}
def detect_type_by_embedding(query_en, alpha=0.8, beta=0.2):
    query_vec = embedder.embed([query_en])[0]
    sims = {
        t: dot(query_vec, vec) / (norm(query_vec) * norm(vec))
        for t, vec in type_embeddings.items()
    }
    keyword_scores = defaultdict(int)
    query_lower = query_en.lower()
    for t, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\\b{re.escape(kw)}\\b", query_lower):
                keyword_scores[t] += 1
    max_kw = max(keyword_scores.values(), default=1)
    keyword_scores_norm = {
        t: keyword_scores[t] / max_kw if max_kw > 0 else 0
        for t in type_embeddings
    }
    final_scores = {
        t: alpha * sims.get(t, 0) + beta * keyword_scores_norm.get(t, 0)
        for t in type_embeddings
    }
    best_type = max(final_scores, key=final_scores.get)
    return best_type

# --- Dịch truy vấn ---
# Load mô hình dịch local nếu có
try:
    model_id = "facebook/nllb-200-distilled-600M"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model_trans = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    translator = pipeline(
        "translation",
        model=model_trans,
        tokenizer=tokenizer,
        src_lang="vie",
        tgt_lang="eng_Latn",
        max_length=512
    )
    def translate_vi_to_en_local(text):
        result = translator(text)
        return result[0]['translation_text']
    USE_LOCAL_TRANSLATE = True
except Exception:
    def translate_vi_to_en_local(text):
        return GoogleTranslator(source='auto', target='en').translate(text)
    USE_LOCAL_TRANSLATE = False

# --- Gemini tóm tắt ---
def summarize_with_gemini(content: str, api_key: str, model: str = "models/gemini-2.0-flash", retrieved_chunks='', user_query='') -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = f"""
    Bạn là một trợ lý AI có nhiệm vụ trả lời câu hỏi của người dùng dựa trên các đoạn thông tin đã được truy xuất từ tài liệu, yêu cầu phải trình bày một cách gọn gàng và đẹp đẽ.
    \nDưới đây là nội dung truy xuất:
    ==== context ====
    {retrieved_chunks}
    ===================
    \nCâu hỏi của người dùng:
    {user_query}
    \nYêu cầu:
    - Chỉ sử dụng thông tin có trong phần \"context\" để trả lời. Có thể điều chỉnh cách ghi lại cho đẹp
    - Nếu câu hỏi yêu cầu nhóm, liệt kê, hoặc so sánh thì hãy xử lý và tổng hợp từ các đoạn context.
    \nTrả lời bằng văn phong ngắn gọn, rõ ràng, chính xác. Trình bày rõ ràng đừng hiện các kí tự của markdown
    """
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        summary = result["candidates"][0]["content"]["parts"][0]["text"]
        return summary.strip()
    except Exception as e:
        return "Lỗi khi gọi API tóm tắt."

def build_classification_prompt(query: str) -> str:
    return f"""
You are an AI assistant helping classify a student's academic query.

## Task:
Given a query (possibly in Vietnamese), you need to:
1. **Translate the query to English** first.
2. Determine the **type** of information being asked (from a fixed set of types).
3. Identify any clearly related **subject codes**. Only return subjects if you're confident.
4. Estimate the **semester** (0–9) if it is clearly implied. Omit this field if unsure.

## Types:
{json.dumps(TYPE_DESCRIPTIONS, indent=2)}

## Subjects:
You are provided a mapping of subject codes to their full names:
{json.dumps(subject_map, indent=2)}

## Output format:
Return a JSON object with these fields:
- `"type"`: One of the predefined type keys.
- `"subjects"`: A list of subject codes (e.g., ["SEG301", "SSL101c"]). Leave empty if not confident.
- `"semester"`: Integer from 0 to 9, **only if confident**. Omit this field if unsure.
- `"query_en"`: The English translation of the input query.

## Original Query:
"{query}"

## Output JSON:
""".strip()

def extract_json_from_markdown(text):
    import re
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    else:
        raise ValueError("Không tìm thấy JSON trong markdown block.")

def analyze_intent_with_gemini(api_key: str, model: str = "models/gemini-2.0-flash", query=''):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = build_classification_prompt(query)
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        summary = result["candidates"][0]["content"]["parts"][0]["text"]
        return extract_json_from_markdown(summary)
    except Exception as e:
        return None

# --- Flask API ---
app = Flask(__name__)
CORS(app)

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({'error': 'Missing query'}), 400
    # 1. Phân tích query bằng Gemini
    analyze = analyze_intent_with_gemini(
        gemini_api_key,
        query=query
    )
    if analyze:
        query_en = analyze.get("query_en", query)
        detected_type = analyze.get("type", None)
        detected_subject = analyze.get("subjects", [])
        detected_semester = analyze.get("semester", None)
    else:
        # fallback nếu Gemini lỗi
        query_en = translate_vi_to_en_local(query)
        detected_type = detect_type_by_embedding(query_en)
        detected_subject = [s[0] for s in detect_subject(query_en)]
        detected_semester = None
    # 2. Vector hóa truy vấn
    if detected_type == 'student_list':
        query_vec = embedder.embed([query])[0]
    else:
        query_vec = embedder.embed([query_en])[0]
    # 3. Tạo filter Qdrant
    query_filter = {"should": [], "must": []}
    if detected_type:
        query_filter["must"].append({"key": "type", "match": {"value": detected_type}})
    if detected_subject:
        for subject_code in detected_subject:
            query_filter["should"].append({
                "key": "subject_code",
                "match": {"value": subject_code}
            })
    if detected_semester:
        query_filter["should"].append({"key": "semester", "match": {"value": detected_semester}})
    # 4. Truy vấn Qdrant
    hits = client.search(
        collection_name="flm_fap",
        query_vector=query_vec.tolist(),
        limit=30,
        query_filter=query_filter if query_filter["must"] or query_filter["should"] else None
    )
    # 5. Tổng hợp kết quả
    results = []
    retrieved_chunks = ''
    for hit in hits:
        payload = hit.payload
        results.append({
            'score': float(f"{hit.score:.4f}"),
            'subject_code': payload.get('subject_code'),
            'subject_name': payload.get('subject_name'),
            'degree_level': payload.get('degree_level'),
            'credits': payload.get('credits'),
            'semester': payload.get('semester'),
            'belong_to_combo': payload.get('belong_to_combo'),
            'pre_requisites': payload.get('pre_requisites'),
            'scoring_scale': payload.get('scoring_scale'),
            'approved': payload.get('approved'),
            'subject_link': payload.get('subject_link'),
            'time_allocation': payload.get('time_allocation'),
            'description': payload.get('description'),
            'student_tasks': payload.get('student_tasks'),
            'tools': payload.get('tools'),
            'note': payload.get('note'),
            'type': payload.get('type'),
            'content': payload.get('content')
        })
        retrieved_chunks += payload.get('content', '') + '\n'
    # 6. Tóm tắt bằng Gemini
    summary = ''
    if results:
        summary = summarize_with_gemini(
            retrieved_chunks,
            gemini_api_key,
            retrieved_chunks=retrieved_chunks,
            user_query=query
        )
    return jsonify({
        'query_translated': query_en,
        'detected_type': detected_type,
        'detected_subject': detected_subject,
        'detected_semester': detected_semester,
        'results': results,
        'summary': summary
    })

if __name__ == '__main__':
    app.run(debug=True) 