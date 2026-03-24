import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import os
import threading


# -----------------------------
# Global YAML state
# -----------------------------
yaml_tab_counter = 0
yaml_tabs_data = {}


# -----------------------------
# Global Pods logs state
# -----------------------------
logs_process = None
logs_thread = None
current_log_pod = None


# -----------------------------
# Output helpers
# -----------------------------
def clear_output():
    output_box.delete("1.0", tk.END)

def write_output(text: str):
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, text)

def append_output(text: str):
    output_box.insert(tk.END, text)

def append_output_threadsafe(text: str):
    root.after(0, lambda: output_box.insert(tk.END, text))

def clear_output_threadsafe():
    root.after(0, lambda: output_box.delete("1.0", tk.END))

def clear_pods_view():
    pods_view_box.delete("1.0", tk.END)

def write_pods_view(text: str):
    pods_view_box.delete("1.0", tk.END)
    pods_view_box.insert(tk.END, text)

def append_pods_view(text: str):
    pods_view_box.insert(tk.END, text)

def append_pods_view_threadsafe(text: str):
    root.after(0, lambda: pods_view_box.insert(tk.END, text))

# -----------------------------
# General lower section reset
# -----------------------------
def reset_yaml_area():
    global yaml_tab_counter, yaml_tabs_data

    stop_logs()

    # Clear YAML search and resources
    entry_yaml_search.delete(0, tk.END)
    yaml_resource_listbox.delete(0, tk.END)

    # Clear pods search and list
    entry_pod_search.delete(0, tk.END)
    pod_listbox.delete(0, tk.END)

    # Close all YAML editor tabs
    for tab_id in yaml_editor_notebook.tabs():
        yaml_editor_notebook.forget(tab_id)

    yaml_tabs_data = {}
    yaml_tab_counter = 0

    clear_output()
    clear_pods_view()


# -----------------------------
# Namespace helpers
# -----------------------------
def get_all_namespaces():
    result = subprocess.run(
        ["kubectl", "get", "namespaces", "-o", "name"],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        raise Exception(result.stderr if result.stderr else "Could not retrieve namespaces.")

    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("namespace/"):
            line = line.replace("namespace/", "", 1)

        items.append(line)

    return items


def find_matching_namespaces(search_text: str):
    items = get_all_namespaces()
    search_text = search_text.strip().lower()

    if not search_text:
        return items

    return [item for item in items if search_text in item.lower()]


def list_namespaces() -> None:
    search_text = entry_namespace_search.get().strip()

    try:
        matches = find_matching_namespaces(search_text)

        namespace_listbox.delete(0, tk.END)
        clear_output()

        if not matches:
            write_output(f"No namespaces found matching: {search_text}\n")
            return

        for item in matches:
            namespace_listbox.insert(tk.END, item)

        write_output(f"Found {len(matches)} namespace(s).\n")

    except FileNotFoundError:
        clear_output()
        write_output("Error: 'kubectl' was not found. Make sure it is installed and available in PATH.\n")
    except Exception as e:
        clear_output()
        write_output(f"Error listing namespaces: {e}\n")


def continue_with_namespace() -> None:
    selection = namespace_listbox.curselection()

    if not selection:
        clear_output()
        write_output("You must select a namespace.\n")
        return

    selected_namespace = namespace_listbox.get(selection[0])
    namespace_var.set(selected_namespace)

    # Clear everything below
    reset_yaml_area()

    write_output(f"Active namespace: {selected_namespace}\n")


# -----------------------------
# YAML / ConfigMaps
# -----------------------------
def get_selected_yaml_kind() -> str:
    kind = yaml_kind_var.get().strip()
    if not kind:
        kind = "configmap"
    return kind


def find_matching_resources(kind: str, search_text: str):
    namespace = namespace_var.get().strip()

    cmd = ["kubectl", "get", kind, "-o", "name"]
    if namespace:
        cmd += ["-n", namespace]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        raise Exception(result.stderr if result.stderr else f"Could not retrieve resources of type {kind}.")

    items = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        if "/" in line:
            resource_name = line.split("/", 1)[1]
        else:
            resource_name = line

        items.append(resource_name)

    search_text = search_text.lower().strip()

    if not search_text:
        return items

    return [item for item in items if search_text in item.lower()]


def list_yaml_resources() -> None:
    kind = get_selected_yaml_kind()
    search_text = entry_yaml_search.get().strip()

    try:
        matches = find_matching_resources(kind, search_text)

        yaml_resource_listbox.delete(0, tk.END)
        clear_output()

        if not matches:
            write_output(f"No '{kind}' resources found matching: {search_text}\n")
            return

        for item in matches:
            yaml_resource_listbox.insert(tk.END, item)

        write_output(
            f"Active namespace: {namespace_var.get().strip() or '(no namespace)'}\n"
            f"Found {len(matches)} resource(s) of type '{kind}'.\n"
        )

    except Exception as e:
        write_output(f"Error listing YAML resources: {e}\n")


def create_yaml_editor_tab(title="New YAML", content="", file_path=None, resource_kind=None, resource_name=None):
    global yaml_tab_counter

    frame = ttk.Frame(yaml_editor_notebook)

    editor = scrolledtext.ScrolledText(
        frame,
        wrap="none",
        undo=True,
        font=("Consolas", 10),
        tabs=("2c",)
    )
    editor.pack(fill="both", expand=True, padx=5, pady=5)
    editor.insert("1.0", content)

    x_scroll = tk.Scrollbar(frame, orient="horizontal", command=editor.xview)
    x_scroll.pack(side="bottom", fill="x")
    editor.configure(xscrollcommand=x_scroll.set)

    if not title:
        yaml_tab_counter += 1
        title = f"YAML {yaml_tab_counter}"

    yaml_editor_notebook.add(frame, text=title)
    yaml_editor_notebook.select(frame)

    yaml_tabs_data[str(frame)] = {
        "editor": editor,
        "file_path": file_path,
        "resource_kind": resource_kind,
        "resource_name": resource_name,
        "dirty": False,
        "title": title
    }

    def on_modified(event=None, frame_ref=frame):
        key = str(frame_ref)
        if key in yaml_tabs_data:
            if editor.edit_modified():
                yaml_tabs_data[key]["dirty"] = True
                current_title = yaml_tabs_data[key]["title"]
                tab_text = yaml_editor_notebook.tab(frame_ref, "text")
                if not tab_text.endswith(" *"):
                    yaml_editor_notebook.tab(frame_ref, text=current_title + " *")
                editor.edit_modified(False)

        apply_yaml_highlighting_to_current()

    editor.edit_modified(False)
    editor.bind("<<Modified>>", on_modified)

    apply_yaml_highlighting(editor)
    return frame


def get_current_yaml_tab():
    current = yaml_editor_notebook.select()
    if not current:
        return None, None
    return current, yaml_tabs_data.get(current)


def get_current_yaml_editor():
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        return None
    return tab_data["editor"]


def apply_yaml_highlighting(editor):
    try:
        content = editor.get("1.0", tk.END)

        editor.tag_remove("yaml_key", "1.0", tk.END)
        editor.tag_remove("yaml_comment", "1.0", tk.END)
        editor.tag_remove("yaml_dash", "1.0", tk.END)
        editor.tag_remove("yaml_string", "1.0", tk.END)

        editor.tag_configure("yaml_key", foreground="#1f4e79")
        editor.tag_configure("yaml_comment", foreground="#6a9955")
        editor.tag_configure("yaml_dash", foreground="#aa5500")
        editor.tag_configure("yaml_string", foreground="#7a3e00")

        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            stripped = line.lstrip()

            if stripped.startswith("#"):
                editor.tag_add("yaml_comment", f"{i}.0", f"{i}.end")
                continue

            dash_pos = line.find("- ")
            if dash_pos != -1:
                editor.tag_add("yaml_dash", f"{i}.{dash_pos}", f"{i}.{dash_pos + 1}")

            if ":" in line and not stripped.startswith("#"):
                key_end = line.find(":")
                if key_end > 0:
                    editor.tag_add("yaml_key", f"{i}.0", f"{i}.{key_end}")

                if key_end + 1 < len(line):
                    rest = line[key_end + 1:].strip()
                    if rest:
                        start_col = line.find(rest, key_end + 1)
                        if start_col != -1:
                            editor.tag_add("yaml_string", f"{i}.{start_col}", f"{i}.end")

    except Exception:
        pass


def apply_yaml_highlighting_to_current():
    editor = get_current_yaml_editor()
    if editor is not None:
        apply_yaml_highlighting(editor)


def load_selected_yaml_resource() -> None:
    selection = yaml_resource_listbox.curselection()

    if not selection:
        write_output("You must select a resource from the list.\n")
        return

    kind = get_selected_yaml_kind()
    resource_name = yaml_resource_listbox.get(selection[0])
    namespace = namespace_var.get().strip()

    cmd = ["kubectl", "get", kind, resource_name, "-o", "yaml"]
    if namespace:
        cmd += ["-n", namespace]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_output()

        if result.returncode != 0:
            write_output(result.stderr if result.stderr else "Could not load the resource.\n")
            return

        create_yaml_editor_tab(
            title=f"{kind}:{resource_name}",
            content=result.stdout,
            resource_kind=kind,
            resource_name=resource_name
        )

        write_output(f"Resource '{kind}/{resource_name}' loaded into a new tab.\n")

    except Exception as e:
        write_output(f"Error loading YAML: {e}\n")


def new_yaml_tab() -> None:
    global yaml_tab_counter
    yaml_tab_counter += 1

    template = """apiVersion: v1
kind: ConfigMap
metadata:
  name: new-configmap
  namespace: default
data:
  example: "value"
"""
    create_yaml_editor_tab(title=f"New YAML {yaml_tab_counter}", content=template)
    write_output("New YAML created.\n")


def open_yaml_file() -> None:
    global yaml_tab_counter

    file_path = filedialog.askopenfilename(
        title="Open YAML file",
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        yaml_tab_counter += 1

        create_yaml_editor_tab(
            title=os.path.basename(file_path),
            content=content,
            file_path=file_path
        )

        write_output(f"File opened: {file_path}\n")

    except Exception as e:
        write_output(f"Error opening YAML file: {e}\n")


def save_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("There is no open YAML tab.\n")
        return

    editor = tab_data["editor"]
    content = editor.get("1.0", tk.END)

    file_path = tab_data["file_path"]

    if not file_path:
        save_current_yaml_tab_as()
        return

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        tab_data["dirty"] = False
        yaml_editor_notebook.tab(current, text=tab_data["title"])

        write_output(f"File saved: {file_path}\n")

    except Exception as e:
        write_output(f"Error saving file: {e}\n")


def save_current_yaml_tab_as() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("There is no open YAML tab.\n")
        return

    file_path = filedialog.asksaveasfilename(
        title="Save YAML as",
        defaultextension=".yaml",
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
    )

    if not file_path:
        return

    editor = tab_data["editor"]
    content = editor.get("1.0", tk.END)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        new_title = os.path.basename(file_path)
        tab_data["file_path"] = file_path
        tab_data["title"] = new_title
        tab_data["dirty"] = False

        yaml_editor_notebook.tab(current, text=new_title)

        write_output(f"File saved as: {file_path}\n")

    except Exception as e:
        write_output(f"Error saving file: {e}\n")


def close_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("There is no open YAML tab.\n")
        return

    if tab_data["dirty"]:
        confirm = messagebox.askyesnocancel(
            "Close tab",
            "This YAML has unsaved changes. Do you want to save before closing?"
        )
        if confirm is None:
            return
        if confirm:
            save_current_yaml_tab()
            current2, _ = get_current_yaml_tab()
            if current2 != current:
                return

    yaml_editor_notebook.forget(current)
    yaml_tabs_data.pop(current, None)

    write_output("YAML tab closed.\n")


def apply_current_yaml_to_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("There is no open YAML tab.\n")
        return

    editor = tab_data["editor"]
    yaml_content = editor.get("1.0", tk.END).strip()

    if not yaml_content:
        write_output("The YAML editor is empty.\n")
        return

    confirm = messagebox.askyesno(
        "Apply YAML",
        "Are you sure you want to apply this YAML to the cluster?"
    )
    if not confirm:
        return

    try:
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=yaml_content,
            capture_output=True,
            text=True,
            check=False
        )

        clear_output()

        if result.stdout:
            append_output(result.stdout + "\n")

        if result.stderr:
            append_output(result.stderr + "\n")

        if result.returncode == 0:
            append_output("YAML applied successfully.\n")
        else:
            append_output("There was an error applying the YAML.\n")

    except Exception as e:
        write_output(f"Error applying YAML: {e}\n")


def reload_current_yaml_from_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("There is no open YAML tab.\n")
        return

    kind = tab_data.get("resource_kind")
    name = tab_data.get("resource_name")

    if not kind or not name:
        write_output("This tab does not come from a cluster resource.\n")
        return

    namespace = namespace_var.get().strip()
    cmd = ["kubectl", "get", kind, name, "-o", "yaml"]
    if namespace:
        cmd += ["-n", namespace]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_output()

        if result.returncode != 0:
            write_output(result.stderr if result.stderr else "Could not reload the resource.\n")
            return

        editor = tab_data["editor"]
        editor.delete("1.0", tk.END)
        editor.insert("1.0", result.stdout)
        editor.edit_modified(False)
        tab_data["dirty"] = False
        yaml_editor_notebook.tab(current, text=tab_data["title"])
        apply_yaml_highlighting(editor)

        write_output(f"Resource '{kind}/{name}' reloaded from the cluster.\n")

    except Exception as e:
        write_output(f"Error reloading YAML: {e}\n")


# -----------------------------
# Pods helpers
# -----------------------------
def get_all_pods():
    namespace = namespace_var.get().strip()

    cmd = ["kubectl", "get", "pods", "-o", "name"]
    if namespace:
        cmd += ["-n", namespace]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        raise Exception(result.stderr if result.stderr else "Could not retrieve pods.")

    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("pod/"):
            line = line.replace("pod/", "", 1)

        items.append(line)

    return items


def find_matching_pods(search_text: str):
    items = get_all_pods()
    search_text = search_text.strip().lower()

    if not search_text:
        return items

    return [item for item in items if search_text in item.lower()]


def list_pods() -> None:
    search_text = entry_pod_search.get().strip()

    try:
        matches = find_matching_pods(search_text)

        pod_listbox.delete(0, tk.END)
        clear_output()

        if not matches:
            write_output(f"No pods found matching: {search_text}\n")
            return

        for item in matches:
            pod_listbox.insert(tk.END, item)

        write_output(
            f"Active namespace: {namespace_var.get().strip() or '(no namespace)'}\n"
            f"Found {len(matches)} pod(s).\n"
        )

    except FileNotFoundError:
        clear_output()
        write_output("Error: 'kubectl' was not found. Make sure it is installed and available in PATH.\n")
    except Exception as e:
        clear_output()
        write_output(f"Error listing pods: {e}\n")


def get_selected_pod():
    selection = pod_listbox.curselection()

    if not selection:
        write_output("You must select a pod from the list.\n")
        return None

    return pod_listbox.get(selection[0])


def describe_selected_pod() -> None:
    pod_name = get_selected_pod()
    if not pod_name:
        return

    stop_logs()

    namespace = namespace_var.get().strip()
    cmd = ["kubectl", "describe", "pod", pod_name]
    if namespace:
        cmd += ["-n", namespace]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_output()

        if result.returncode != 0:
            write_output(result.stderr if result.stderr else "Could not describe the pod.\n")
            return

        write_output(result.stdout)

    except Exception as e:
        write_output(f"Error describing pod: {e}\n")


def read_logs_worker(process):
    global logs_process

    try:
        for line in process.stdout:
            if process != logs_process:
                break
            append_pods_view_threadsafe(line)

        stderr_text = process.stderr.read()
        if stderr_text:
            append_pods_view_threadsafe("\n" + stderr_text)

    except Exception as e:
        append_pods_view_threadsafe(f"\nError reading logs: {e}\n")


def start_logs_selected_pod() -> None:
    global logs_process, logs_thread, current_log_pod

    pod_name = get_selected_pod()
    if not pod_name:
        return

    stop_logs()

    namespace = namespace_var.get().strip()
    tail_value = entry_log_tail.get().strip()

    cmd = ["kubectl", "logs", "-f", pod_name]

    if namespace:
        cmd += ["-n", namespace]

    if tail_value:
        cmd += ["--tail", tail_value]

    try:
        clear_pods_view()
        write_pods_view(f"Streaming logs for pod: {pod_name}\n\n")

        logs_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        current_log_pod = pod_name
        logs_thread = threading.Thread(target=read_logs_worker, args=(logs_process,), daemon=True)
        logs_thread.start()

    except Exception as e:
        write_pods_view(f"Error starting live logs: {e}\n")


def stop_logs() -> None:
    global logs_process, logs_thread, current_log_pod

    if logs_process is not None:
        try:
            logs_process.terminate()
        except Exception:
            pass

        logs_process = None
        logs_thread = None
        current_log_pod = None


def show_previous_logs_selected_pod() -> None:
    pod_name = get_selected_pod()
    if not pod_name:
        return

    stop_logs()

    namespace = namespace_var.get().strip()
    tail_value = entry_log_tail.get().strip()

    cmd = ["kubectl", "logs", pod_name]

    if namespace:
        cmd += ["-n", namespace]

    if tail_value:
        cmd += ["--tail", tail_value]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_pods_view()

        if result.returncode != 0:
            write_pods_view(result.stderr if result.stderr else "Could not retrieve pod logs.\n")
            return

        write_pods_view(result.stdout if result.stdout else "No logs available.\n")

    except Exception as e:
        write_pods_view(f"Error retrieving logs: {e}\n")


# -----------------------------
# UI
# -----------------------------
root = tk.Tk()
root.title("Mini Kubernetes UI - YAML Studio")
root.state("zoomed")  # Full screen on Windows / most systems

# -----------------------------
# MAIN SCROLLABLE CONTAINER
# -----------------------------
main_canvas = tk.Canvas(root, highlightthickness=0, bd=0)
main_scrollbar = tk.Scrollbar(root, orient="vertical", command=main_canvas.yview)

main_canvas.configure(yscrollcommand=main_scrollbar.set)

main_scrollbar.pack(side="right", fill="y")
main_canvas.pack(side="left", fill="both", expand=True)

main_container = tk.Frame(main_canvas)
canvas_window = main_canvas.create_window((0, 0), window=main_container, anchor="nw")

def update_scrollregion(event=None):
    main_canvas.configure(scrollregion=main_canvas.bbox("all"))

def resize_canvas_content(event):
    main_canvas.itemconfig(canvas_window, width=event.width)

main_container.bind("<Configure>", update_scrollregion)
main_canvas.bind("<Configure>", resize_canvas_content)

def on_mousewheel(event):
    main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

main_canvas.bind_all("<MouseWheel>", on_mousewheel)

# Hidden / logical active namespace
namespace_var = tk.StringVar(value="slfsvc-twa07")

# ---------------------------------
# Namespace Selector
# ---------------------------------
namespace_selector_frame = tk.LabelFrame(main_container, text="Namespace Selector")
namespace_selector_frame.pack(fill="x", padx=10, pady=5)

namespace_search_row = tk.Frame(namespace_selector_frame)
namespace_search_row.pack(fill="x", padx=5, pady=5)

tk.Label(namespace_search_row, text="Search namespace:").pack(side=tk.LEFT, padx=5)

entry_namespace_search = tk.Entry(namespace_search_row, width=60)
entry_namespace_search.pack(side=tk.LEFT, padx=5)

tk.Button(namespace_search_row, text="List Namespaces", command=list_namespaces).pack(side=tk.LEFT, padx=5)
tk.Button(namespace_search_row, text="Continue", command=continue_with_namespace).pack(side=tk.LEFT, padx=5)

namespace_current_label = tk.Label(namespace_search_row, textvariable=namespace_var, relief="sunken", width=50, anchor="w")
namespace_current_label.pack(side=tk.RIGHT, padx=5)

tk.Label(namespace_search_row, text="Active namespace:").pack(side=tk.RIGHT, padx=5)

namespace_list_frame = tk.Frame(namespace_selector_frame)
namespace_list_frame.pack(fill="x", padx=5, pady=5)

tk.Label(namespace_list_frame, text="Matches:").pack(anchor="w")

namespace_listbox = tk.Listbox(namespace_list_frame, height=4)
namespace_listbox.pack(fill="x", pady=5)

# ---------------------------------
# Tabs
# ---------------------------------
tabs = ttk.Notebook(main_container)
tab_yaml = ttk.Frame(tabs)
tab_pods = ttk.Frame(tabs)

tabs.add(tab_yaml, text="ConfigMaps / YAML Studio")
tabs.add(tab_pods, text="Pods")
tabs.pack(fill="both", padx=10, pady=10)

# Top controls
yaml_top_frame = tk.Frame(tab_yaml)
yaml_top_frame.pack(fill="x", padx=5, pady=5)

tk.Label(yaml_top_frame, text="Type:").pack(side=tk.LEFT, padx=5)

yaml_kind_var = tk.StringVar(value="configmap")
yaml_kind_combo = ttk.Combobox(
    yaml_top_frame,
    textvariable=yaml_kind_var,
    width=18,
    state="readonly",
    values=[
        "configmap",
        "deployment",
        "service",
        "secret",
        "ingress",
        "job",
        "cronjob",
        "statefulset",
        "daemonset"
    ]
)
yaml_kind_combo.pack(side=tk.LEFT, padx=5)

tk.Label(yaml_top_frame, text="Search:").pack(side=tk.LEFT, padx=5)

entry_yaml_search = tk.Entry(yaml_top_frame, width=60)
entry_yaml_search.pack(side=tk.LEFT, padx=5)

tk.Button(yaml_top_frame, text="List", command=list_yaml_resources).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_top_frame, text="Open Selected", command=load_selected_yaml_resource).pack(side=tk.LEFT, padx=5)

# Listbox
yaml_middle_frame = tk.Frame(tab_yaml)
yaml_middle_frame.pack(fill="x", padx=5, pady=5)

tk.Label(yaml_middle_frame, text="Matches:").pack(anchor="w")

yaml_resource_listbox = tk.Listbox(yaml_middle_frame, height=4)
yaml_resource_listbox.pack(fill="both", expand=True, pady=5)
yaml_resource_listbox.bind("<Double-Button-1>", lambda event: load_selected_yaml_resource())

# Actions
yaml_actions_frame = tk.Frame(tab_yaml)
yaml_actions_frame.pack(fill="x", padx=5, pady=5)

tk.Button(yaml_actions_frame, text="New YAML", command=new_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Open File", command=open_yaml_file).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Save", command=save_current_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Save As", command=save_current_yaml_tab_as).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Apply to Cluster", command=apply_current_yaml_to_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Reload from Cluster", command=reload_current_yaml_from_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Close Tab", command=close_current_yaml_tab).pack(side=tk.LEFT, padx=5)

# Editor notebook
yaml_editor_notebook = ttk.Notebook(tab_yaml)
yaml_editor_notebook.pack(fill="both", padx=5, pady=5)

# ---------------------------------
# Pods tab
# ---------------------------------
pods_top_frame = tk.Frame(tab_pods)
pods_top_frame.pack(fill="x", padx=5, pady=5)

tk.Label(pods_top_frame, text="Search pod:").pack(side=tk.LEFT, padx=5)

entry_pod_search = tk.Entry(pods_top_frame, width=60)
entry_pod_search.pack(side=tk.LEFT, padx=5)

tk.Button(pods_top_frame, text="List Pods", command=list_pods).pack(side=tk.LEFT, padx=5)
tk.Button(pods_top_frame, text="Describe Selected", command=describe_selected_pod).pack(side=tk.LEFT, padx=5)

# Matches list
pods_middle_frame = tk.Frame(tab_pods)
pods_middle_frame.pack(fill="x", padx=5, pady=5)

tk.Label(pods_middle_frame, text="Matches:").pack(anchor="w")

pod_listbox = tk.Listbox(pods_middle_frame, height=6)
pod_listbox.pack(fill="both", expand=True, pady=5)
pod_listbox.bind("<Double-Button-1>", lambda event: describe_selected_pod())

# Logs actions
pods_logs_frame = tk.Frame(tab_pods)
pods_logs_frame.pack(fill="x", padx=5, pady=5)

tk.Label(pods_logs_frame, text="Tail:").pack(side=tk.LEFT, padx=5)

entry_log_tail = tk.Entry(pods_logs_frame, width=10)
entry_log_tail.pack(side=tk.LEFT, padx=5)
entry_log_tail.insert(0, "100")

tk.Button(pods_logs_frame, text="View Logs", command=show_previous_logs_selected_pod).pack(side=tk.LEFT, padx=5)
tk.Button(pods_logs_frame, text="Live Logs", command=start_logs_selected_pod).pack(side=tk.LEFT, padx=5)
tk.Button(pods_logs_frame, text="Stop Logs", command=stop_logs).pack(side=tk.LEFT, padx=5)

# Central Pods viewer
pods_view_frame = tk.LabelFrame(tab_pods, text="Pod Describe / Logs")
pods_view_frame.pack(fill="both", expand=True, padx=5, pady=5)

pods_view_box = scrolledtext.ScrolledText(
    pods_view_frame,
    wrap="none",
    height=20,
    font=("Consolas", 10)
)
pods_view_box.pack(fill="both", expand=True, padx=5, pady=5)

# Output
output_frame = tk.LabelFrame(main_container, text="Output / Messages")
output_frame.pack(fill="x", padx=10, pady=10)

output_box = scrolledtext.ScrolledText(output_frame, height=12, wrap="none")
output_box.pack(fill="both", padx=5, pady=5)

def on_close():
    stop_logs()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()