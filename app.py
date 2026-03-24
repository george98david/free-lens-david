import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import os


# -----------------------------
# Helpers de salida
# -----------------------------
def clear_top():
    top_box.delete("1.0", tk.END)

def clear_main():
    main_box.delete("1.0", tk.END)

def clear_bottom():
    bottom_box.delete("1.0", tk.END)

def clear_all_outputs():
    clear_top()
    clear_main()
    clear_bottom()

def write_top(text: str):
    top_box.delete("1.0", tk.END)
    top_box.insert(tk.END, text)

def write_main(text: str):
    main_box.delete("1.0", tk.END)
    main_box.insert(tk.END, text)

def write_bottom(text: str):
    bottom_box.delete("1.0", tk.END)
    bottom_box.insert(tk.END, text)

def append_bottom(text: str):
    bottom_box.insert(tk.END, text)


# -----------------------------
# Helper para ejecutar kubectl
# -----------------------------
def run_kubectl(cmd: str) -> None:
    try:
        namespace = namespace_var.get().strip()

        full_cmd = ["kubectl"] + cmd.split()
        if namespace:
            full_cmd += ["-n", namespace]

        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_main()
        clear_bottom()

        if result.stdout:
            write_main(result.stdout)

        if result.stderr:
            write_bottom("\n[stderr]\n" + result.stderr)

        if not result.stdout and not result.stderr:
            write_bottom("Sin salida.\n")

    except FileNotFoundError:
        write_bottom("Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n")
    except Exception as e:
        write_bottom(f"Error inesperado: {e}\n")


# -----------------------------
# PODS
# -----------------------------
def find_matching_pods(search_text: str):
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
        raise Exception(result.stderr if result.stderr else "No se pudieron obtener los pods.")

    pods = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("pod/"):
            line = line.replace("pod/", "", 1)
        if line:
            pods.append(line)

    search_text = search_text.lower().strip()

    if not search_text:
        return pods

    matches = [pod for pod in pods if search_text in pod.lower()]
    return matches


def list_pods() -> None:
    search_text = entry_pod.get().strip()

    try:
        matches = find_matching_pods(search_text)

        pod_listbox.delete(0, tk.END)
        clear_top()

        if not matches:
            write_top(f"No se encontraron pods con: {search_text}\n")
            return

        for pod in matches:
            pod_listbox.insert(tk.END, pod)

        namespace = namespace_var.get().strip() or "(sin namespace)"
        write_top(f"Se encontraron {len(matches)} pod(s) en namespace '{namespace}'.\n")

    except Exception as e:
        write_top(f"Error listando pods: {e}\n")


def get_selected_pod():
    selection = pod_listbox.curselection()

    if not selection:
        write_top("Debes seleccionar un pod de la lista.\n")
        return None

    return pod_listbox.get(selection[0])


def pod_logs() -> None:
    pod = get_selected_pod()
    if not pod:
        return

    namespace = namespace_var.get().strip()

    try:
        cmd = ["kubectl", "logs", pod]
        if namespace:
            cmd += ["-n", namespace]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_main()

        if result.returncode != 0:
            write_main(result.stderr if result.stderr else f"No se pudieron obtener logs de {pod}\n")
            return

        write_main(result.stdout if result.stdout else "Sin logs.\n")

    except Exception as e:
        write_main(f"Error: {e}\n")


def pod_describe() -> None:
    pod = get_selected_pod()
    if not pod:
        return

    namespace = namespace_var.get().strip()

    try:
        cmd = ["kubectl", "describe", "pod", pod]
        if namespace:
            cmd += ["-n", namespace]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        clear_bottom()

        if result.returncode != 0:
            write_bottom(result.stderr if result.stderr else f"No se pudo describir el pod {pod}\n")
            return

        write_bottom(result.stdout if result.stdout else "Sin describe.\n")

    except Exception as e:
        write_bottom(f"Error: {e}\n")


def pod_logs_follow() -> None:
    pod = get_selected_pod()
    if not pod:
        return

    namespace = namespace_var.get().strip()

    cmd = ["kubectl", "logs", "-f", pod]
    if namespace:
        cmd += ["-n", namespace]

    try:
        clear_main()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        current_process["proc"] = process
        main_box.insert(tk.END, f"Siguiendo logs de {pod}...\n\n")

        def stream_output():
            proc = current_process["proc"]
            if proc is None:
                return

            line = proc.stdout.readline()
            if line:
                main_box.insert(tk.END, line)
                main_box.see(tk.END)
                root.after(50, stream_output)
            else:
                if proc.poll() is None:
                    root.after(100, stream_output)
                else:
                    main_box.insert(tk.END, "\n\nProceso finalizado.\n")
                    current_process["proc"] = None

        stream_output()

    except FileNotFoundError:
        write_main("Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n")
    except Exception as e:
        write_main(f"Error inesperado: {e}\n")


def stop_follow() -> None:
    proc = current_process["proc"]
    if proc is not None and proc.poll() is None:
        proc.terminate()
        current_process["proc"] = None
        main_box.insert(tk.END, "\n\nSeguimiento detenido.\n")
    else:
        main_box.insert(tk.END, "\nNo hay ningún proceso en seguimiento.\n")


# -----------------------------
# Otras acciones
# -----------------------------
def list_deployments() -> None:
    run_kubectl("get deployments -o wide")

def run_custom() -> None:
    cmd = entry_custom.get().strip()
    if not cmd:
        write_bottom("Ingresa un comando kubectl.\n")
        return
    run_kubectl(cmd)

def clear_output() -> None:
    clear_all_outputs()

def list_namespaces() -> None:
    run_kubectl("get namespaces")

def get_services() -> None:
    run_kubectl("get svc -o wide")

def get_nodes() -> None:
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "wide"],
            capture_output=True,
            text=True,
            check=False
        )

        clear_main()
        clear_bottom()

        if result.stdout:
            write_main(result.stdout)

        if result.stderr:
            write_bottom("\n[stderr]\n" + result.stderr)

        if not result.stdout and not result.stderr:
            write_bottom("Sin salida.\n")

    except FileNotFoundError:
        write_bottom("Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n")
    except Exception as e:
        write_bottom(f"Error inesperado: {e}\n")


def on_close() -> None:
    proc = current_process["proc"]
    if proc is not None and proc.poll() is None:
        if messagebox.askyesno("Salir", "Hay un proceso de logs en ejecución. ¿Deseas cerrarlo y salir?"):
            proc.terminate()
            root.destroy()
    else:
        root.destroy()


# -----------------------------
# ConfigMaps / YAML
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
        raise Exception(result.stderr if result.stderr else f"No se pudieron obtener recursos de tipo {kind}.")

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
        clear_top()

        if not matches:
            write_top(f"No se encontraron recursos '{kind}' con: {search_text}\n")
            return

        for item in matches:
            yaml_resource_listbox.insert(tk.END, item)

        write_top(f"Se encontraron {len(matches)} recurso(s) de tipo '{kind}'.\n")

    except Exception as e:
        write_top(f"Error listando recursos YAML: {e}\n")


yaml_tab_counter = 0
yaml_tabs_data = {}


def create_yaml_editor_tab(title="Nuevo YAML", content="", file_path=None, resource_kind=None, resource_name=None):
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

    yaml_tab_counter += 1
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
        write_top("Debes seleccionar un recurso de la lista.\n")
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

        if result.returncode != 0:
            write_bottom(result.stderr if result.stderr else "No se pudo cargar el recurso.\n")
            return

        create_yaml_editor_tab(
            title=f"{kind}:{resource_name}",
            content=result.stdout,
            resource_kind=kind,
            resource_name=resource_name
        )

        write_bottom(f"Recurso '{kind}/{resource_name}' cargado en un nuevo tab.\n")

    except Exception as e:
        write_bottom(f"Error cargando YAML: {e}\n")


def new_yaml_tab() -> None:
    template = """apiVersion: v1
kind: ConfigMap
metadata:
  name: nuevo-configmap
  namespace: default
data:
  ejemplo: "valor"
"""
    create_yaml_editor_tab(title="Nuevo YAML", content=template)
    write_bottom("Nuevo YAML creado.\n")


def open_yaml_file() -> None:
    file_path = filedialog.askopenfilename(
        title="Abrir archivo YAML",
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        create_yaml_editor_tab(
            title=os.path.basename(file_path),
            content=content,
            file_path=file_path
        )

        write_bottom(f"Archivo abierto: {file_path}\n")

    except Exception as e:
        write_bottom(f"Error abriendo archivo YAML: {e}\n")


def save_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_bottom("No hay ningún tab YAML abierto.\n")
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

        write_bottom(f"Archivo guardado: {file_path}\n")

    except Exception as e:
        write_bottom(f"Error guardando archivo: {e}\n")


def save_current_yaml_tab_as() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_bottom("No hay ningún tab YAML abierto.\n")
        return

    file_path = filedialog.asksaveasfilename(
        title="Guardar YAML como",
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

        write_bottom(f"Archivo guardado como: {file_path}\n")

    except Exception as e:
        write_bottom(f"Error guardando archivo: {e}\n")


def close_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_bottom("No hay ningún tab YAML abierto.\n")
        return

    if tab_data["dirty"]:
        confirm = messagebox.askyesnocancel(
            "Cerrar tab",
            "Este YAML tiene cambios sin guardar. ¿Quieres guardarlo antes de cerrar?"
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

    write_bottom("Tab YAML cerrado.\n")


def apply_current_yaml_to_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_bottom("No hay ningún tab YAML abierto.\n")
        return

    editor = tab_data["editor"]
    yaml_content = editor.get("1.0", tk.END).strip()

    if not yaml_content:
        write_bottom("El editor YAML está vacío.\n")
        return

    confirm = messagebox.askyesno(
        "Aplicar YAML",
        "¿Seguro que quieres aplicar este YAML al cluster?"
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

        clear_bottom()

        if result.stdout:
            append_bottom(result.stdout + "\n")

        if result.stderr:
            append_bottom(result.stderr + "\n")

        if result.returncode == 0:
            append_bottom("YAML aplicado correctamente.\n")
        else:
            append_bottom("Hubo un error al aplicar el YAML.\n")

    except Exception as e:
        write_bottom(f"Error aplicando YAML: {e}\n")


def reload_current_yaml_from_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_bottom("No hay ningún tab YAML abierto.\n")
        return

    kind = tab_data.get("resource_kind")
    name = tab_data.get("resource_name")

    if not kind or not name:
        write_bottom("Este tab no viene de un recurso del cluster.\n")
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

        if result.returncode != 0:
            write_bottom(result.stderr if result.stderr else "No se pudo recargar el recurso.\n")
            return

        editor = tab_data["editor"]
        editor.delete("1.0", tk.END)
        editor.insert("1.0", result.stdout)
        editor.edit_modified(False)
        tab_data["dirty"] = False
        yaml_editor_notebook.tab(current, text=tab_data["title"])
        apply_yaml_highlighting(editor)

        write_bottom(f"Recurso '{kind}/{name}' recargado desde el cluster.\n")

    except Exception as e:
        write_bottom(f"Error recargando YAML: {e}\n")


# -----------------------------
# UI Setup
# -----------------------------
root = tk.Tk()
root.title("Mini Kubernetes UI - Avanzado")
root.geometry("1000x700")

current_process = {"proc": None}

# Namespace frame
namespace_frame = tk.Frame(root)
namespace_frame.pack(pady=5)

tk.Label(namespace_frame, text="Namespace: ").pack(side=tk.LEFT)

namespace_var = tk.StringVar()
namespace_entry = tk.Entry(namespace_frame, textvariable=namespace_var, width=20)
namespace_entry.pack(side=tk.LEFT, padx=5)
namespace_var.set("slfsvc-twa07")

tk.Button(namespace_frame, text="Listar Namespaces", command=list_namespaces).pack(side=tk.LEFT, padx=5)
tk.Button(namespace_frame, text="Ver Services", command=get_services).pack(side=tk.LEFT, padx=5)
tk.Button(namespace_frame, text="Ver Nodes", command=get_nodes).pack(side=tk.LEFT, padx=5)
tk.Button(namespace_frame, text="Limpiar salida", command=clear_output).pack(side=tk.LEFT, padx=5)

# Tabs
tabs = ttk.Notebook(root)
tab_pods = ttk.Frame(tabs)
tab_deploy = ttk.Frame(tabs)
tab_custom = ttk.Frame(tabs)
tab_yaml = ttk.Frame(tabs)

tabs.add(tab_pods, text="Pods")
tabs.add(tab_deploy, text="Deployments")
tabs.add(tab_custom, text="Comandos")
tabs.add(tab_yaml, text="YAML Studio")
tabs.pack(expand=1, fill="both", padx=10, pady=10)

# -----------------------------
# PODS TAB
# -----------------------------
pods_top_frame = tk.Frame(tab_pods)
pods_top_frame.pack(fill="x", padx=10, pady=10)

tk.Label(pods_top_frame, text="Buscar pod:").pack(side=tk.LEFT, padx=5)

entry_pod = tk.Entry(pods_top_frame, width=40)
entry_pod.pack(side=tk.LEFT, padx=5)

tk.Button(pods_top_frame, text="Listar Pods", command=list_pods).pack(side=tk.LEFT, padx=5)
tk.Button(pods_top_frame, text="Ver Logs", command=pod_logs).pack(side=tk.LEFT, padx=5)
tk.Button(pods_top_frame, text="Seguir Logs (-f)", command=pod_logs_follow).pack(side=tk.LEFT, padx=5)
tk.Button(pods_top_frame, text="Detener Logs", command=stop_follow).pack(side=tk.LEFT, padx=5)
tk.Button(pods_top_frame, text="Describe Pod", command=pod_describe).pack(side=tk.LEFT, padx=5)

pods_middle_frame = tk.Frame(tab_pods)
pods_middle_frame.pack(fill="x", padx=10, pady=5)

tk.Label(pods_middle_frame, text="Coincidencias:").pack(anchor="w")

pod_listbox = tk.Listbox(pods_middle_frame, height=8)
pod_listbox.pack(fill="x", pady=5)

# doble click = logs
pod_listbox.bind("<Double-Button-1>", lambda event: pod_logs())

# -----------------------------
# DEPLOYMENTS TAB
# -----------------------------
tk.Button(tab_deploy, text="Listar Deployments", command=list_deployments).pack(pady=10)

# -----------------------------
# CUSTOM COMMANDS TAB
# -----------------------------
tk.Label(tab_custom, text="kubectl <comando> (sin escribir 'kubectl'):").pack(pady=5)

entry_custom = tk.Entry(tab_custom, width=70)
entry_custom.pack(pady=5)

tk.Button(tab_custom, text="Ejecutar", command=run_custom).pack(pady=5)

# -----------------------------
# YAML STUDIO TAB
# -----------------------------
yaml_top_frame = tk.Frame(tab_yaml)
yaml_top_frame.pack(fill="x", padx=5, pady=5)

tk.Label(yaml_top_frame, text="Tipo:").pack(side=tk.LEFT, padx=5)

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

tk.Label(yaml_top_frame, text="Buscar:").pack(side=tk.LEFT, padx=5)

entry_yaml_search = tk.Entry(yaml_top_frame, width=30)
entry_yaml_search.pack(side=tk.LEFT, padx=5)

tk.Button(yaml_top_frame, text="Listar", command=list_yaml_resources).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_top_frame, text="Abrir seleccionado", command=load_selected_yaml_resource).pack(side=tk.LEFT, padx=5)

yaml_middle_frame = tk.Frame(tab_yaml)
yaml_middle_frame.pack(fill="x", padx=5, pady=5)

tk.Label(yaml_middle_frame, text="Coincidencias:").pack(anchor="w")

yaml_resource_listbox = tk.Listbox(yaml_middle_frame, height=6)
yaml_resource_listbox.pack(fill="x", pady=5)
yaml_resource_listbox.bind("<Double-Button-1>", lambda event: load_selected_yaml_resource())

yaml_actions_frame = tk.Frame(tab_yaml)
yaml_actions_frame.pack(fill="x", padx=5, pady=5)

tk.Button(yaml_actions_frame, text="Nuevo YAML", command=new_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Abrir archivo", command=open_yaml_file).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Guardar", command=save_current_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Guardar como", command=save_current_yaml_tab_as).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Aplicar al cluster", command=apply_current_yaml_to_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Recargar desde cluster", command=reload_current_yaml_from_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Cerrar tab", command=close_current_yaml_tab).pack(side=tk.LEFT, padx=5)

yaml_editor_notebook = ttk.Notebook(tab_yaml)
yaml_editor_notebook.pack(fill="both", expand=True, padx=5, pady=5)

# -----------------------------
# OUTPUT AREAS
# -----------------------------
output_container = tk.Frame(root)
output_container.pack(padx=10, pady=10, fill="both", expand=True)

top_frame = tk.LabelFrame(output_container, text="Listas / Resultados")
top_frame.pack(fill="both", expand=True, pady=4)

top_box = scrolledtext.ScrolledText(top_frame, width=120, height=10, wrap="none")
top_box.pack(fill="both", expand=True, padx=5, pady=5)

main_frame = tk.LabelFrame(output_container, text="Logs / Contenido principal")
main_frame.pack(fill="both", expand=True, pady=4)

main_box = scrolledtext.ScrolledText(main_frame, width=120, height=14, wrap="none")
main_box.pack(fill="both", expand=True, padx=5, pady=5)

bottom_frame = tk.LabelFrame(output_container, text="Describe / Mensajes")
bottom_frame.pack(fill="both", expand=True, pady=4)

bottom_box = scrolledtext.ScrolledText(bottom_frame, width=120, height=8, wrap="none")
bottom_box.pack(fill="both", expand=True, padx=5, pady=5)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()