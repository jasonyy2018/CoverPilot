from config import DEMO_TITLE, IS_SHARE, CV_EXT, EXT_TXT
from config import CHEAP_API_BASE, CHEAP_API_KEY, CHEAP_MODEL
from config import STRONG_API_BASE, STRONG_API_KEY, STRONG_MODEL
from util import is_valid_url
from util import mylogger
from util import stream_together
from taskNonAI import extract_url, file_to_html
from taskAI import TaskAI
## load data
from data_test import mock_jd, mock_cv
## ui
import gradio as gr
## dependency
from pypandoc.pandoc_download import download_pandoc
## std
import os


logger = mylogger(__name__,'%(asctime)s:%(levelname)s:%(message)s')
info = logger.info

def init():
    os.system("shot-scraper install -b firefox")
    download_pandoc()

def prepare_input(jd_info, cv_file: str, cv_text):
    if jd_info:
        if is_valid_url(jd_info):
            jd = extract_url(jd_info)
        else:
            jd = jd_info
    else:
        jd = mock_jd

    if cv_text:
        cv = cv_text
    elif cv_file:
        if any([cv_file.endswith(ext) for ext in EXT_TXT]):
            with open(cv_file, "r", encoding="utf8") as f:
                cv = f.read()
        else:
            cv = file_to_html(cv_file)
    else:
        cv = mock_cv
    return jd, cv

def run_refine(api_base, api_key, api_model, jd_info, cv_text):
    jd,cv=jd_info,cv_text
    cheapAPI = {"base": api_base, "key": api_key, "model": api_model}
    taskAI = TaskAI(cheapAPI, temperature=0.2, max_tokens=2048)  # max_tokens=2048
    info("API initialized")
    gen = (
        taskAI.jd_preprocess(input=jd),
        taskAI.cv_preprocess(input=cv),
    )
    info("tasks initialized")
    result = [""] * 2
    while 1:
        stop: bool = True
        for i in range(len(gen)):
            try:
                result[i] += next(gen[i]).delta
                stop = False
            except StopIteration:
                # info(f"gen[{i}] exhausted")
                pass
        yield result
        if stop:
            info("tasks done")
            break

def run_compose(api_base, api_key, api_model, min_jd, min_cv):
    strongAPI = {"base": api_base, "key": api_key, "model": api_model}
    taskAI = TaskAI(strongAPI, temperature=0.6, max_tokens=4000)
    info("Composing letter with CoT ...")
    result = ""
    for response in taskAI.compose_letter_CoT(jd=min_jd, resume=min_cv):
        result += response.delta
        yield result

def finalize_letter_txt(api_base, api_key, api_model, debug_CoT, jd, cv):
    cheapAPI = {"base": api_base, "key": api_key, "model": api_model}
    taskAI = TaskAI(cheapAPI, temperature=0.2, max_tokens=2048)
    info("Finalizing letter ...")
    gen = stream_together(
        taskAI.purify_letter(full_text=debug_CoT),
        taskAI.get_jobapp_meta(JD=jd, CV=cv),
    )
    for result in gen:
        yield result

with gr.Blocks(
    title=DEMO_TITLE,
    theme=gr.themes.Base(primary_hue="blue", secondary_hue="sky", neutral_hue="slate"),
) as app:
    intro = f"""# {DEMO_TITLE}
    > You provide job description and résumé. I write Cover letter for you!
    Before you use, please fisrt setup API for 2 AI agents': Cheap AI and Strong AI.
    """
    gr.Markdown(intro)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("AI setup (OpenAI-compatible LLM API)", open=False):
                gr.Markdown(
                    "**Cheap AI**, an honest format converter and refiner, extracts essential info from job description and résumé, to reduce subsequent cost on Strong AI."
                )
                with gr.Group():
                    cheap_base = gr.Textbox(
                        value=CHEAP_API_BASE, label="API BASE"
                    )
                    cheap_key = gr.Textbox(value=CHEAP_API_KEY, label="API key")
                    cheap_model = gr.Textbox(value=CHEAP_MODEL, label="Model ID")
                gr.Markdown(
                    "---\n**Strong AI**, a thoughtful wordsmith, generates perfect cover letters to make both you and recruiters happy."
                )
                with gr.Group():
                    strong_base = gr.Textbox(
                        value=STRONG_API_BASE, label="API BASE"
                    )
                    strong_key = gr.Textbox(
                        value=STRONG_API_KEY, label="API key", type="password"
                    )
                    strong_model = gr.Textbox(value=STRONG_MODEL, label="Model ID")
            with gr.Group():
                gr.Markdown("## Employer - Job Description")
                jd_info = gr.Textbox(
                    label="Job Description",
                    placeholder="Paste as Full Text (recommmend) or URL",
                    lines=5,
                    max_lines=10,
                )
            with gr.Group():
                gr.Markdown("## Applicant - CV / Résumé")
                with gr.Row():
                    cv_file = gr.File(
                        label="Allowed formats: " + " ".join(CV_EXT),
                        file_count="single",
                        file_types=CV_EXT,
                        type="filepath",
                    )
                    cv_text = gr.TextArea(
                        label="Or enter text",
                        placeholder="If attempting to both upload a file and enter text, only this text will be used.",
                    )
        with gr.Column(scale=2):
            gr.Markdown("## Result")
            with gr.Accordion("Reformatting", open=True) as reformat_zone:
                with gr.Row():
                    min_jd = gr.TextArea(label="Reformatted Job Description")
                    min_cv = gr.TextArea(label="Reformatted CV / Résumé")
            with gr.Accordion("Expert Zone", open=False) as expert_zone:
                
                debug_CoT = gr.Textbox(label="Chain of Thoughts")
                debug_jobapp = gr.Textbox(label="Job application meta data")
            cover_letter_text = gr.Textbox(label="Cover Letter")
            cover_letter_pdf = gr.File(
                label="Cover Letter PDF",
                file_count="single",
                file_types=[".pdf"],
                type="filepath",
            )
            infer_btn = gr.Button("Go!", variant="primary")
            

    infer_btn.click(
        fn=prepare_input,
        inputs=[jd_info, cv_file, cv_text],
        outputs=[jd_info, cv_text]
    ).then(
        fn=run_refine,
        inputs=[cheap_base, cheap_key, cheap_model, jd_info, cv_text],
        outputs=[min_jd, min_cv],
    ).then(fn=lambda:[gr.Accordion("Expert Zone", open=True),gr.Accordion("Reformatting", open=False)],inputs=None, outputs=[expert_zone, reformat_zone]
    ).then(fn=run_compose, inputs=[strong_base, strong_key, strong_model, min_jd, min_cv], outputs=[debug_CoT]                      
    ).then(fn=lambda:gr.Accordion("Expert Zone", open=False),inputs=None, outputs=[expert_zone]
    ).then(fn=finalize_letter_txt, inputs=[cheap_base, cheap_key, cheap_model, debug_CoT, jd_info, cv_text], outputs=[cover_letter_text, debug_jobapp]
    )


if __name__ == "__main__":
    init()
    app.queue(max_size=10, default_concurrency_limit=1).launch(
        show_error=True, debug=True, share=IS_SHARE
    )