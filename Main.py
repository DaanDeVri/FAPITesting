# -*- coding: utf-8 -*-
import gradio as gr
import requests
import json
import re
import os
import time


def safe_convert(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8', errors='replace')
    return str(value)


def process_path_variables(url, params):
    path_params = {}
    new_params = []
    variables = re.findall(r'\{(\w+)\}|:(\w+)', url)
    variables = [v[0] or v[1] for v in variables]
    for key, value in params or []:
        if key and value:
            key = safe_convert(key).strip()
            value = safe_convert(value).strip()
            if key in variables:
                path_params[key] = value
            else:
                new_params.append([key, value])
    for key, val in path_params.items():
        url = re.sub(rf'\{{{key}\}}|:{key}', val, url)
    return url, new_params


def prepare_request_args(method, url, params, headers, body_type=None,
                         json_body=None, form_params=None,
                         file_key=None, uploaded_file=None):
    # 1) Path variables and filter params
    resolved_url, filtered_params = process_path_variables(url, params)
    params_dict = {k: v for k, v in filtered_params if k and v}

    # 2) Headers
    headers_dict = {}
    for active, k, v in headers or []:
        if active and k and v:
            headers_dict[k.strip()] = v.strip()

    # 3) Body
    json_data = None
    data = None
    files = None
    if method.upper() in ["POST", "PUT", "PATCH"]:
        if body_type == "JSON" and json_body and json_body.strip():
            json_data = json.loads(json_body)
            headers_dict.setdefault("Content-Type", "application/json")
        else:
            data = {k: v for k, v in form_params or [] if k and v}
            if uploaded_file and file_key and file_key.strip():
                fname = os.path.basename(uploaded_file.name)
                files = {file_key.strip(): (fname, open(uploaded_file.name, 'rb'))}
            else:
                headers_dict.setdefault("Content-Type", "application/x-www-form-urlencoded")

    return resolved_url, params_dict, headers_dict, json_data, data, files

# --- Core request sender ---
def send_request(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file):
    try:
        original_url = url
        resolved_url, filtered = process_path_variables(url, params)
        params_dict = {k: v for k, v in filtered if k and v}
        headers_dict = {}
        for active, k, v in headers or []:
            if active and k and v:
                headers_dict[safe_convert(k).strip()] = safe_convert(v).strip()

        # prepare body
        json_data = None
        data = None
        files = None
        if method.upper() in ["POST", "PUT", "PATCH"]:
            if body_type == "JSON" and json_body and json_body.strip():
                json_data = json.loads(json_body)
                headers_dict.setdefault("Content-Type", "application/json")
            else:
                data = {k: v for k, v in form_params or [] if k and v}
                if uploaded_file and file_key and file_key.strip():
                    fname = os.path.basename(uploaded_file.name)
                    files = {file_key.strip(): (fname, open(uploaded_file.name, 'rb'))}

                else:
                    headers_dict.setdefault("Content-Type", "application/x-www-form-urlencoded")

        resp = requests.request(
            method=method,
            url=resolved_url,
            params=params_dict,
            headers=headers_dict,
            json=json_data,
            data=data,
            files=files,
            timeout=15
        )
        resp.encoding = 'utf-8'
        try:
            body = resp.json()
        except:
            body = resp.text
        return json.dumps({
            "request": {
                "method": method,
                "url": original_url,
                "resolved_url": resp.url,
                "query_params": params_dict,
                "headers": headers_dict,
                "body_type": body_type,
                "body": json_data if body_type == "JSON" else {"form_data": data, "files": list(files.keys()) if files else []}
            },
            "response": {"status": resp.status_code, "headers": dict(resp.headers), "body": body}
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": "Request Error", "details": safe_convert(e)}, indent=2)

# --- Test utilities ---
def validate_status(method, url, params=None, headers=None, expected=200,
                    body_type=None, json_body=None, form_params=None,
                    file_key=None, uploaded_file=None):
    resolved_url, params_dict, headers_dict, json_data, data, files = prepare_request_args(
        method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file
    )
    r = requests.request(method=method, url=resolved_url,
                         params=params_dict, headers=headers_dict,
                         json=json_data, data=data, files=files, timeout=15)
    return (r.status_code == expected, r.status_code)

def test_functional(method, url, params=None, headers=None,
                    body_type=None, json_body=None, form_params=None,
                    file_key=None, uploaded_file=None):
    ok, status = validate_status(method, url, params, headers, 200,
                                 body_type, json_body, form_params, file_key, uploaded_file)
    return f"Functional: {method} {url} -> {status} ({'PASS' if ok else 'FAIL'})"

def test_error_handling(method, url, params=None, headers=None,
                        body_type=None, json_body=None, form_params=None,
                        file_key=None, uploaded_file=None):
    resolved_url, params_dict, headers_dict, _, _, _ = prepare_request_args(
        method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file
    )
    bad_url = resolved_url.rstrip('/') + "/nonexistent"
    r = requests.request(method="GET", url=bad_url,
                         params=params_dict, headers=headers_dict)
    return f"Error Handling: GET {bad_url} -> {r.status_code}"

def test_performance(method, url, params=None, headers=None,
                     body_type=None, json_body=None, form_params=None,
                     file_key=None, uploaded_file=None, iterations=5):
    resolved_url, params_dict, headers_dict, json_data, data, files = prepare_request_args(
        method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file
    )
    times = []
    for _ in range(iterations):
        s = time.time()
        requests.request(method=method, url=resolved_url,
                         params=params_dict, headers=headers_dict,
                         json=json_data, data=data, files=files)
        times.append(time.time() - s)
    return f"Performance: Avg {sum(times)/len(times):.3f}s over {iterations} calls"

def test_security(method, url, params=None, headers=None,
                  body_type=None, json_body=None, form_params=None,
                  file_key=None, uploaded_file=None):

    resolved_url, params_dict, headers_dict, json_data, data, files = prepare_request_args(
        method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file
    )

    r_with_auth = requests.request(method=method, url=resolved_url,
                                   params=params_dict, headers=headers_dict,
                                   json=json_data, data=data, files=files)
    status_with_auth = r_with_auth.status_code


    headers_dict_no_auth = headers_dict.copy()
    headers_dict_no_auth.pop("Authorization", None)


    r_no_auth = requests.request(method=method, url=resolved_url,
                                 params=params_dict, headers=headers_dict_no_auth,
                                 json=json_data, data=data, files=files)
    status_no_auth = r_no_auth.status_code

    if status_with_auth != status_no_auth:
        return f"Security: Missing auth -> {status_no_auth} (Expected: {status_with_auth}) ✅"
    else:
        return f"Security: No auth -> {status_no_auth} ⚠️ Check endpoint access control"


# --- Runners ---
def run_all_tests(method, url, params, headers,
                  body_type=None, json_body=None, form_params=None,
                  file_key=None, uploaded_file=None):
    return "\n".join([
        test_functional(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file),
        test_error_handling(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file),
        test_performance(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file),
        test_security(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file)
    ])

def run_selected_tests(method, url, params, headers, test_type,
                       body_type=None, json_body=None, form_params=None,
                       file_key=None, uploaded_file=None):
    if test_type == "Ручное тестирование":
        return "Manual testing: use your tool to send requests."
    if test_type == "Автоматизированное тестирование":
        return "\n".join([
            test_functional(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file),
            test_error_handling(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file)
        ])
    if test_type == "Нагрузочное тестирование":
        return test_performance(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file)
    if test_type == "Тестирование безопасности":
        return test_security(method, url, params, headers, body_type, json_body, form_params, file_key, uploaded_file)
    return "Unknown test type"

# --- Tools & UI ---
tools_by_type = {
    "Ручное тестирование": ["Postman", "Insomnia", "Swagger"],
    "Автоматизированное тестирование": ["pytest", "JUnit", "RestAssured"],
    "Нагрузочное тестирование": ["JMeter", "Gatling"],
    "Тестирование безопасности": ["OWASP ZAP", "Burp Suite"]
}

def update_tool_options(tt):
    return gr.update(choices=tools_by_type[tt], value=tools_by_type[tt][0])

with gr.Blocks(title="API Tester with Tests") as app:
    gr.Markdown("""# 🧪 API Tester + Test Suite""")
    with gr.Row():
        test_type = gr.Dropdown(list(tools_by_type.keys()), value="Ручное тестирование", label="Тип тестирования")
        tool_sel  = gr.Dropdown(tools_by_type["Ручное тестирование"], value=tools_by_type["Ручное тестирование"][0], label="Инструмент")
        test_type.change(update_tool_options, inputs=test_type, outputs=tool_sel)
    with gr.Row():
        method = gr.Dropdown(["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"], value="GET", label="HTTP Method")
        url    = gr.Textbox(label="URL Endpoint", placeholder="https://api.example.com/{id}", max_lines=1, scale=4)
    with gr.Tabs():
        with gr.Tab("Params & Headers"):
            params  = gr.Dataframe(headers=["Key","Value"], col_count=(2,"fixed"), row_count=(1,"dynamic"), type="array", label="Parameters")
            headers = gr.Dataframe(headers=["✅","Header","Value"], col_count=(3,"fixed"),row_count=(1,"dynamic"), type="array", label="Headers", datatype=["bool","str","str"])
        with gr.Tab("Body"):
            body_type = gr.Radio(["JSON","Form Data"], value="JSON", label="Body Type")
            with gr.Group() as json_grp:
                json_body = gr.Code(label="JSON Body", language="json", lines=10)
            with gr.Group(visible=False) as form_grp:
                form_params   = gr.Dataframe(headers=["Key","Value"], col_count=(2,"fixed"), row_count=(1,"dynamic"), type="array", label="Form Data")
                file_key      = gr.Textbox(label="File Key")
                uploaded_file = gr.File(label="Upload File", file_count="single")
            body_type.change(lambda t: ([gr.update(visible=True), gr.update(visible=False)] if t=="JSON" else [gr.update(visible=False), gr.update(visible=True)]), inputs=body_type, outputs=[json_grp, form_grp])
    with gr.Row():
        clear_btn  = gr.Button("Clear")
        send_btn   = gr.Button("Send Request", variant="primary")
        sel_btn    = gr.Button("Run Selected Tests")
        all_btn    = gr.Button("Run All Tests")
    with gr.Accordion("Response", open=True):
        output = gr.Code(label="Result", language="json", lines=15)
    with gr.Accordion("Test Results", open=False):
        test_out = gr.Textbox(label="Tests", lines=10)
    clear_btn.click(lambda: ("GET","",[["",""]],[[False,"",""]],"JSON","",[["",""]],"",None), outputs=[method,url,params,headers,body_type,json_body,form_params,file_key,uploaded_file])
    send_btn.click(send_request, inputs=[method,url,params,headers,body_type,json_body,form_params,file_key,uploaded_file], outputs=output)
    sel_btn.click(run_selected_tests, inputs=[method,url,params,headers,test_type,body_type,json_body,form_params,file_key,uploaded_file], outputs=test_out)
    all_btn.click(run_all_tests, inputs=[method,url,params,headers,body_type,json_body,form_params,file_key,uploaded_file], outputs=test_out)

if __name__ == "__main__":
    app.launch(server_port=7860, share=True)
