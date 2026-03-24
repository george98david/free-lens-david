import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import os


# -----------------------------
# Estado global YAML
# -----------------------------
yaml_tab_counter = 0
yaml_tabs_data = {}


# -----------------------------
# Helpers de salida
# -----------------------------
def clear_output():
    output_box.delete("1.0", tk.END)

def write_output(text: str):
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, text)

def append_output(text: str):
    output_box.insert(tk.END, text)


# -----------------------------
# Reset general inferior
# -----------------------------
def reset_yaml_area():
    global yaml_tab_counter, yaml_tabs_data

    # limpiar búsqueda y lista de recursos
    entry_yaml_search.delete(0, tk.END)
    yaml_resource_listbox.delete(0, tk.END)

    # cerrar todos los tabs del editor YAML
    for tab_id in yaml_editor_notebook.tabs():
        yaml_editor_notebook.forget(tab_id)

    yaml_tabs_data = {}
    yaml_tab_counter = 0

    clear_output()


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
        raise Exception(result.stderr if result.stderr else "No se pudieron obtener los namespaces.")

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
        namespace_status_box.delete("1.0", tk.END)

        if not matches:
            namespace_status_box.insert(tk.END, f"No se encontraron namespaces con: {search_text}\n")
            return

        for item in matches:
            namespace_listbox.insert(tk.END, item)

        namespace_status_box.insert(tk.END, f"Se encontraron {len(matches)} namespace(s).\n")

    except FileNotFoundError:
        namespace_status_box.delete("1.0", tk.END)
        namespace_status_box.insert(tk.END, "Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n")
    except Exception as e:
        namespace_status_box.delete("1.0", tk.END)
        namespace_status_box.insert(tk.END, f"Error listando namespaces: {e}\n")


def continue_with_namespace() -> None:
    selection = namespace_listbox.curselection()

    if not selection:
        namespace_status_box.delete("1.0", tk.END)
        namespace_status_box.insert(tk.END, "Debes seleccionar un namespace.\n")
        return

    selected_namespace = namespace_listbox.get(selection[0])
    namespace_var.set(selected_namespace)

    # Limpiar todo lo de abajo
    reset_yaml_area()

    write_output(f"Namespace activo: {selected_namespace}\n")


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
        clear_output()

        if not matches:
            write_output(f"No se encontraron recursos '{kind}' con: {search_text}\n")
            return

        for item in matches:
            yaml_resource_listbox.insert(tk.END, item)

        write_output(
            f"Namespace activo: {namespace_var.get().strip() or '(sin namespace)'}\n"
            f"Se encontraron {len(matches)} recurso(s) de tipo '{kind}'.\n"
        )

    except Exception as e:
        write_output(f"Error listando recursos YAML: {e}\n")


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
        write_output("Debes seleccionar un recurso de la lista.\n")
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
            write_output(result.stderr if result.stderr else "No se pudo cargar el recurso.\n")
            return

        create_yaml_editor_tab(
            title=f"{kind}:{resource_name}",
            content=result.stdout,
            resource_kind=kind,
            resource_name=resource_name
        )

        write_output(f"Recurso '{kind}/{resource_name}' cargado en un nuevo tab.\n")

    except Exception as e:
        write_output(f"Error cargando YAML: {e}\n")


def new_yaml_tab() -> None:
    global yaml_tab_counter
    yaml_tab_counter += 1

    template = """apiVersion: v1
kind: ConfigMap
metadata:
  name: nuevo-configmap
  namespace: default
data:
  ejemplo: "valor"
"""
    create_yaml_editor_tab(title=f"Nuevo YAML {yaml_tab_counter}", content=template)
    write_output("Nuevo YAML creado.\n")


def open_yaml_file() -> None:
    global yaml_tab_counter

    file_path = filedialog.askopenfilename(
        title="Abrir archivo YAML",
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

        write_output(f"Archivo abierto: {file_path}\n")

    except Exception as e:
        write_output(f"Error abriendo archivo YAML: {e}\n")


def save_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("No hay ningún tab YAML abierto.\n")
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

        write_output(f"Archivo guardado: {file_path}\n")

    except Exception as e:
        write_output(f"Error guardando archivo: {e}\n")


def save_current_yaml_tab_as() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("No hay ningún tab YAML abierto.\n")
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

        write_output(f"Archivo guardado como: {file_path}\n")

    except Exception as e:
        write_output(f"Error guardando archivo: {e}\n")


def close_current_yaml_tab() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("No hay ningún tab YAML abierto.\n")
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

    write_output("Tab YAML cerrado.\n")


def apply_current_yaml_to_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("No hay ningún tab YAML abierto.\n")
        return

    editor = tab_data["editor"]
    yaml_content = editor.get("1.0", tk.END).strip()

    if not yaml_content:
        write_output("El editor YAML está vacío.\n")
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

        clear_output()

        if result.stdout:
            append_output(result.stdout + "\n")

        if result.stderr:
            append_output(result.stderr + "\n")

        if result.returncode == 0:
            append_output("YAML aplicado correctamente.\n")
        else:
            append_output("Hubo un error al aplicar el YAML.\n")

    except Exception as e:
        write_output(f"Error aplicando YAML: {e}\n")


def reload_current_yaml_from_cluster() -> None:
    current, tab_data = get_current_yaml_tab()
    if not current or not tab_data:
        write_output("No hay ningún tab YAML abierto.\n")
        return

    kind = tab_data.get("resource_kind")
    name = tab_data.get("resource_name")

    if not kind or not name:
        write_output("Este tab no viene de un recurso del cluster.\n")
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
            write_output(result.stderr if result.stderr else "No se pudo recargar el recurso.\n")
            return

        editor = tab_data["editor"]
        editor.delete("1.0", tk.END)
        editor.insert("1.0", result.stdout)
        editor.edit_modified(False)
        tab_data["dirty"] = False
        yaml_editor_notebook.tab(current, text=tab_data["title"])
        apply_yaml_highlighting(editor)

        write_output(f"Recurso '{kind}/{name}' recargado desde el cluster.\n")

    except Exception as e:
        write_output(f"Error recargando YAML: {e}\n")


# -----------------------------
# UI
# -----------------------------
root = tk.Tk()
root.title("Mini Kubernetes UI - YAML Studio")
root.geometry("1100x760")

# Namespace activo oculto / lógico
namespace_var = tk.StringVar(value="")

# ---------------------------------
# Selector de Namespace (nuevo)
# ---------------------------------
namespace_selector_frame = tk.LabelFrame(root, text="Selector de Namespace")
namespace_selector_frame.pack(fill="x", padx=10, pady=10)

namespace_search_row = tk.Frame(namespace_selector_frame)
namespace_search_row.pack(fill="x", padx=5, pady=5)

tk.Label(namespace_search_row, text="Buscar namespace:").pack(side=tk.LEFT, padx=5)

entry_namespace_search = tk.Entry(namespace_search_row, width=35)
entry_namespace_search.pack(side=tk.LEFT, padx=5)

tk.Button(namespace_search_row, text="Listar Namespaces", command=list_namespaces).pack(side=tk.LEFT, padx=5)
tk.Button(namespace_search_row, text="Continuar", command=continue_with_namespace).pack(side=tk.LEFT, padx=5)

namespace_current_label = tk.Label(namespace_search_row, textvariable=namespace_var, relief="sunken", width=30, anchor="w")
namespace_current_label.pack(side=tk.RIGHT, padx=5)

tk.Label(namespace_search_row, text="Namespace activo:").pack(side=tk.RIGHT, padx=5)

namespace_list_frame = tk.Frame(namespace_selector_frame)
namespace_list_frame.pack(fill="x", padx=5, pady=5)

tk.Label(namespace_list_frame, text="Coincidencias:").pack(anchor="w")

namespace_listbox = tk.Listbox(namespace_list_frame, height=6)
namespace_listbox.pack(fill="x", pady=5)

namespace_status_frame = tk.Frame(namespace_selector_frame)
namespace_status_frame.pack(fill="x", padx=5, pady=5)

namespace_status_box = scrolledtext.ScrolledText(namespace_status_frame, width=120, height=4, wrap="none")
namespace_status_box.pack(fill="both", expand=True)

# ---------------------------------
# Tabs
# ---------------------------------
tabs = ttk.Notebook(root)
tab_yaml = ttk.Frame(tabs)

tabs.add(tab_yaml, text="ConfigMaps / YAML Studio")
tabs.pack(expand=1, fill="both", padx=10, pady=10)

# Top controls
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

# Listbox
yaml_middle_frame = tk.Frame(tab_yaml)
yaml_middle_frame.pack(fill="x", padx=5, pady=5)

tk.Label(yaml_middle_frame, text="Coincidencias:").pack(anchor="w")

yaml_resource_listbox = tk.Listbox(yaml_middle_frame, height=6)
yaml_resource_listbox.pack(fill="x", pady=5)
yaml_resource_listbox.bind("<Double-Button-1>", lambda event: load_selected_yaml_resource())

# Actions
yaml_actions_frame = tk.Frame(tab_yaml)
yaml_actions_frame.pack(fill="x", padx=5, pady=5)

tk.Button(yaml_actions_frame, text="Nuevo YAML", command=new_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Abrir archivo", command=open_yaml_file).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Guardar", command=save_current_yaml_tab).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Guardar como", command=save_current_yaml_tab_as).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Aplicar al cluster", command=apply_current_yaml_to_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Recargar desde cluster", command=reload_current_yaml_from_cluster).pack(side=tk.LEFT, padx=5)
tk.Button(yaml_actions_frame, text="Cerrar tab", command=close_current_yaml_tab).pack(side=tk.LEFT, padx=5)

# Editor notebook
yaml_editor_notebook = ttk.Notebook(tab_yaml)
yaml_editor_notebook.pack(fill="both", expand=True, padx=5, pady=5)

# Output
output_frame = tk.LabelFrame(root, text="Salida / Mensajes")
output_frame.pack(fill="both", expand=True, padx=10, pady=10)

output_box = scrolledtext.ScrolledText(output_frame, width=120, height=10, wrap="none")
output_box.pack(fill="both", expand=True, padx=5, pady=5)

root.mainloop()