"""Request-scoped resume pipeline used by the local web demo.

The legacy CLI is intentionally untouched.  This adapter has no mutable global
model selection: every invocation receives an immutable PipelineConfig and
returns structured artifacts suitable for an EvaluationRun.
"""
from __future__ import annotations

import hashlib, json, os, re, time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import fitz
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / '.env')
load_dotenv(PROJECT_ROOT / 'web_demo' / '.env', override=True)

@dataclass(frozen=True)
class PipelineConfig:
    provider: str = "ollama"
    model_id: str = "gemma3:4b"
    temperature: float = 0.1
    top_p: float = 0.9
    prompt_version: str = "web-v1"
    github_enrichment: bool = True
    force_fresh: bool = False
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

@dataclass
class StageResult:
    name: str; status: str; duration_ms: int; note: str = ""; artifact: dict[str, Any] | None = None

@dataclass
class PipelineResult:
    status: str; score: float | None; base: float | None; bonus: float | None; deduction: float | None
    resume: dict[str, Any]; evidence: dict[str, list[str]]; stages: list[StageResult]; raw_text: str
    config: PipelineConfig
    def to_json(self) -> dict[str, Any]:
        value=asdict(self); value['config']=asdict(self.config); return value

def _stage(stages, name, fn):
    start=time.perf_counter()
    try:
        value=fn(); stages.append(StageResult(name,"COMPLETED",int((time.perf_counter()-start)*1000),artifact=value if isinstance(value,dict) else None)); return value
    except Exception as exc:
        stages.append(StageResult(name,"FAILED",int((time.perf_counter()-start)*1000),str(exc))); raise

def _extract(path: Path) -> str:
    doc=fitz.open(path)
    try: return "\n".join(page.get_text("text") for page in doc).strip()
    finally: doc.close()

def _parse(text: str) -> dict[str, Any]:
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    email=(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text) or [None])[0]
    github=(re.search(r"(?:https?://)?github\.com/[\w-]+",text,re.I) or [None])[0]
    skills=[item for item in ["Python","Go","Java","JavaScript","TypeScript","FastAPI","Kubernetes","Docker","SQL","AWS","PyTorch","React","Spring","Kafka"] if re.search(r"\b"+re.escape(item)+r"\b",text,re.I)]
    name=lines[0][:80] if lines else "Uploaded candidate"
    return {"basics":{"name":name,"email":email},"skills":skills,"github":github,"text_length":len(text),"work":lines[1:6]}

def _heuristic_evaluate(text: str, resume: dict[str,Any]) -> tuple[float,float,float,float,dict[str,list[str]]]:
    lower=text.lower(); skills=resume['skills']; production=sum(word in lower for word in ['production','deployed','scale','latency','kubernetes','customer'])
    projects=sum(word in lower for word in ['project','github','open source','built'])
    base=min(84.0, 28+len(skills)*4+production*5+projects*3)
    bonus=6.0 if resume.get('github') else 1.0
    deduction=0.0 if len(text)>500 else 4.0
    score=max(0.0,min(100.0,base+bonus-deduction))
    strengths=[f"Identified skills: {', '.join(skills[:5]) or 'not clearly stated'}.",f"Resume contains {len(text.split())} extracted words."]
    improvements=[] if len(text)>500 else ["Add more detail about project outcomes and impact."]
    return round(score,1),round(base,1),bonus,deduction,{"strengths":strengths,"improvements":improvements or ["Human review recommended before a hiring decision."]}

def _llm_evaluate(text: str, resume: dict[str, Any], config: PipelineConfig):
    """Call an explicitly selected provider.  It never mutates global defaults."""
    prompt=("Evaluate this resume for human prioritization. Return JSON only with "
            "base, bonus, deduction, strengths (array), improvements (array). "
            "All numeric values must be 0..100; base plus bonus minus deduction is final score.\n\n"+text[:24000])
    if config.provider in ('deepseek', 'dashscope', 'openai_compatible'):
        import requests
        prefix = 'DASHSCOPE' if config.provider == 'dashscope' else 'DEEPSEEK'
        base=os.environ[f'{prefix}_BASE_URL'].rstrip('/')
        response=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+os.environ[f'{prefix}_API_KEY'],'Content-Type':'application/json'},json={'model':config.model_id,'messages':[{'role':'user','content':prompt}],'temperature':config.temperature,'top_p':config.top_p,'response_format':{'type':'json_object'}},timeout=90)
        response.raise_for_status(); content=response.json()['choices'][0]['message']['content']
    else:
        import ollama
        client=ollama.Client(host=os.getenv('OLLAMA_BASE_URL','http://127.0.0.1:11434'))
        content=client.chat(model=config.model_id,messages=[{'role':'user','content':prompt}],options={'temperature':config.temperature,'top_p':config.top_p},format='json')['message']['content']
    data=json.loads(content);base=float(data['base']);bonus=float(data.get('bonus',0));deduction=float(data.get('deduction',0));score=max(0,min(100,base+bonus-deduction))
    return round(score,1),base,bonus,deduction,{'strengths':[str(x) for x in data.get('strengths',[])][:5] or ['Model returned no strengths.'],'improvements':[str(x) for x in data.get('improvements',[])][:5] or ['Human review recommended.']}

def _evaluate(text: str, resume: dict[str,Any], config: PipelineConfig):
    try:
        if config.provider in ('deepseek','dashscope','openai_compatible'):
            prefix = 'DASHSCOPE' if config.provider == 'dashscope' else 'DEEPSEEK'
            if not all(os.getenv(f'{prefix}_{key}') for key in ('API_KEY','BASE_URL','MODEL')):
                raise RuntimeError(f'{prefix} is not configured')
        return _llm_evaluate(text,resume,config)
    except Exception as exc:
        score,base,bonus,deduction,evidence=_heuristic_evaluate(text,resume)
        evidence['improvements'].append(f'Provider fallback used: {type(exc).__name__}.')
        return score,base,bonus,deduction,evidence

def run_resume_pipeline(pdf_path: str | Path, config: PipelineConfig) -> PipelineResult:
    stages=[]; path=Path(pdf_path)
    if not path.exists(): raise FileNotFoundError(path)
    raw=_stage(stages,"PDF_TEXT_EXTRACTION",lambda:_extract(path))
    if not raw: raise ValueError("PDF contains no extractable text")
    resume=_stage(stages,"RESUME_SECTION_PARSE",lambda:_parse(raw))
    score,base,bonus,deduction,evidence=_stage(stages,"EVALUATION",lambda:{"value":_evaluate(raw,resume,config)})["value"]
    stages.append(StageResult("RANK_AND_PERSIST","COMPLETED",0,"Ready for staff review"))
    return PipelineResult("COMPLETED",score,base,bonus,deduction,resume,evidence,stages,raw,config)

def provider_registry() -> list[dict[str,Any]]:
    ollama_url=os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434")
    installed=False
    try:
        import requests
        installed=any(item.get('name')==os.getenv('OLLAMA_MODEL','gemma3:4b') for item in requests.get(ollama_url+'/api/tags',timeout=1).json().get('models',[]))
    except Exception: pass
    configured=bool(os.getenv('DEEPSEEK_API_KEY') and os.getenv('DEEPSEEK_BASE_URL') and os.getenv('DEEPSEEK_MODEL'))
    dashscope_configured=bool(os.getenv('DASHSCOPE_API_KEY') and os.getenv('DASHSCOPE_BASE_URL') and os.getenv('DASHSCOPE_MODEL'))
    return [
      {"id":os.getenv('OLLAMA_MODEL','gemma3:4b'),"name":"Gemma 3 4B","provider":"Ollama","type":"Local","healthy":installed,"installed":installed,"structured":True,"availability":"Available" if installed else "Ollama/model unavailable"},
      {"id":os.getenv('DEEPSEEK_MODEL','deepseek'),"name":"DeepSeek","provider":"DeepSeek","type":"Cloud","healthy":configured,"installed":configured,"structured":True,"availability":"Configured" if configured else "Not configured"},
      {"id":os.getenv('DASHSCOPE_MODEL','qwen-plus'),"name":"Alibaba DashScope","provider":"DashScope","type":"Cloud","healthy":dashscope_configured,"installed":dashscope_configured,"structured":True,"availability":"Configured" if dashscope_configured else "Not configured"},
    ]
