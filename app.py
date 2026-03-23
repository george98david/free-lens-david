import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess


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

        output_box.delete("1.0", tk.END)

        if result.stdout:
            output_box.insert(tk.END, result.stdout)

        if result.stderr:
            output_box.insert(tk.END, "\n[stderr]\n" + result.stderr)

        if not result.stdout and not result.stderr:
            output_box.insert(tk.END, "Sin salida.\n")

    except FileNotFoundError:
        output_box.delete("1.0", tk.END)
        output_box.insert(
            tk.END,
            "Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n"
        )
    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error inesperado: {e}\n")


# -----------------------------
# Acciones
# -----------------------------
def list_pods() -> None:
    search_text = entry_pod.get().strip().lower()
    namespace = namespace_var.get().strip()

    try:
        cmd = ["kubectl", "get", "pods", "-o", "wide"]
        if namespace:
            cmd += ["-n", namespace]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        output_box.delete("1.0", tk.END)

        if result.returncode != 0:
            output_box.insert(tk.END, result.stderr)
            return

        lines = result.stdout.splitlines()

        if not lines:
            output_box.insert(tk.END, "No hay pods.\n")
            return

        # encabezado
        output_box.insert(tk.END, lines[0] + "\n")

        # filtrar si hay texto
        if search_text:
            filtered = [line for line in lines[1:] if search_text in line.lower()]
        else:
            filtered = lines[1:]

        if not filtered:
            output_box.insert(tk.END, f"\nNo hay pods que coincidan con '{search_text}'\n")
            return

        for line in filtered:
            output_box.insert(tk.END, line + "\n")

    except Exception as e:
        output_box.insert(tk.END, f"\nError: {e}\n")


def list_deployments() -> None:
    run_kubectl("get deployments -o wide")


def pod_logs() -> None:
    search_text = entry_pod.get().strip()

    if not search_text or search_text == "nombre-del-pod":
        output_box.insert(tk.END, "\nDebes ingresar parte del nombre del pod.\n")
        return

    try:
        matches = find_matching_pods(search_text)

        if not matches:
            output_box.delete("1.0", tk.END)
            output_box.insert(tk.END, f"No se encontraron pods que coincidan con: {search_text}\n")
            return

        if len(matches) > 1:
            output_box.delete("1.0", tk.END)
            output_box.insert(tk.END, f"Se encontraron varios pods para '{search_text}':\n\n")
            for pod in matches:
                output_box.insert(tk.END, f"- {pod}\n")
            output_box.insert(tk.END, "\nEscribe algo más específico.\n")
            return

        pod = matches[0]
        run_kubectl(f"logs {pod}")

    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error: {e}\n")


def pod_describe() -> None:
    search_text = entry_pod.get().strip()

    if not search_text or search_text == "nombre-del-pod":
        output_box.insert(tk.END, "\nDebes ingresar parte del nombre del pod.\n")
        return

    try:
        matches = find_matching_pods(search_text)

        if not matches:
            output_box.delete("1.0", tk.END)
            output_box.insert(tk.END, f"No se encontraron pods que coincidan con: {search_text}\n")
            return

        if len(matches) > 1:
            output_box.delete("1.0", tk.END)
            output_box.insert(tk.END, f"Se encontraron varios pods para '{search_text}':\n\n")
            for pod in matches:
                output_box.insert(tk.END, f"- {pod}\n")
            output_box.insert(tk.END, "\nEscribe algo más específico.\n")
            return

        pod = matches[0]
        run_kubectl(f"describe pod {pod}")

    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error: {e}\n")


def pod_logs_follow() -> None:
    pod = entry_pod.get().strip()
    if not pod or pod == "nombre-del-pod":
        output_box.insert(tk.END, "\nDebes ingresar el nombre del pod.\n")
        return

    namespace = namespace_var.get().strip()

    cmd = ["kubectl", "logs", "-f", pod]
    if namespace:
        cmd += ["-n", namespace]

    try:
        output_box.delete("1.0", tk.END)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        current_process["proc"] = process
        output_box.insert(tk.END, f"Siguiendo logs de {pod}...\n\n")

        def stream_output():
            proc = current_process["proc"]
            if proc is None:
                return

            line = proc.stdout.readline()
            if line:
                output_box.insert(tk.END, line)
                output_box.see(tk.END)
                root.after(50, stream_output)
            else:
                if proc.poll() is None:
                    root.after(100, stream_output)
                else:
                    output_box.insert(tk.END, "\n\nProceso finalizado.\n")
                    current_process["proc"] = None

        stream_output()

    except FileNotFoundError:
        output_box.delete("1.0", tk.END)
        output_box.insert(
            tk.END,
            "Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n"
        )
    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error inesperado: {e}\n")


def stop_follow() -> None:
    proc = current_process["proc"]
    if proc is not None and proc.poll() is None:
        proc.terminate()
        current_process["proc"] = None
        output_box.insert(tk.END, "\n\nSeguimiento detenido.\n")
    else:
        output_box.insert(tk.END, "\nNo hay ningún proceso en seguimiento.\n")


def run_custom() -> None:
    cmd = entry_custom.get().strip()
    if not cmd:
        output_box.insert(tk.END, "\nIngresa un comando kubectl.\n")
        return
    run_kubectl(cmd)


def clear_output() -> None:
    output_box.delete("1.0", tk.END)


def list_namespaces() -> None:
    run_kubectl("get namespaces")


def get_services() -> None:
    run_kubectl("get svc -o wide")


def get_nodes() -> None:
    # Para nodes no suele aplicar namespace, así que ejecutamos directo
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "wide"],
            capture_output=True,
            text=True,
            check=False
        )

        output_box.delete("1.0", tk.END)

        if result.stdout:
            output_box.insert(tk.END, result.stdout)

        if result.stderr:
            output_box.insert(tk.END, "\n[stderr]\n" + result.stderr)

        if not result.stdout and not result.stderr:
            output_box.insert(tk.END, "Sin salida.\n")

    except FileNotFoundError:
        output_box.delete("1.0", tk.END)
        output_box.insert(
            tk.END,
            "Error: no se encontró 'kubectl'. Verifica que esté instalado y en el PATH.\n"
        )
    except Exception as e:
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, f"Error inesperado: {e}\n")


def on_close() -> None:
    proc = current_process["proc"]
    if proc is not None and proc.poll() is None:
        if messagebox.askyesno("Salir", "Hay un proceso de logs en ejecución. ¿Deseas cerrarlo y salir?"):
            proc.terminate()
            root.destroy()
    else:
        root.destroy()

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

    search_text = search_text.lower()
    matches = [pod for pod in pods if search_text in pod.lower()]

    return matches

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

tabs.add(tab_pods, text="Pods")
tabs.add(tab_deploy, text="Deployments")
tabs.add(tab_custom, text="Comandos")
tabs.pack(expand=1, fill="both", padx=10, pady=10)

# -----------------------------
# PODS TAB
# -----------------------------
tk.Button(tab_pods, text="Listar Pods", command=list_pods).pack(pady=5)

entry_pod = tk.Entry(tab_pods, width=40)
entry_pod.pack(pady=5)
entry_pod.insert(0, "nombre-del-pod")

tk.Button(tab_pods, text="Ver Logs", command=pod_logs).pack(pady=2)
tk.Button(tab_pods, text="Seguir Logs (-f)", command=pod_logs_follow).pack(pady=2)
tk.Button(tab_pods, text="Detener Logs", command=stop_follow).pack(pady=2)
tk.Button(tab_pods, text="Describe Pod", command=pod_describe).pack(pady=2)

# -----------------------------
# DEPLOYMENTS TAB
# -----------------------------
tk.Button(tab_deploy, text="Listar Deployments", command=list_deployments).pack(pady=5)

# -----------------------------
# CUSTOM COMMANDS TAB
# -----------------------------
tk.Label(tab_custom, text="kubectl <comando> (sin escribir 'kubectl'):").pack(pady=5)

entry_custom = tk.Entry(tab_custom, width=70)
entry_custom.pack(pady=5)

tk.Button(tab_custom, text="Ejecutar", command=run_custom).pack(pady=5)

# -----------------------------
# OUTPUT WINDOW
# -----------------------------
output_box = scrolledtext.ScrolledText(root, width=120, height=28)
output_box.pack(padx=10, pady=10, fill="both", expand=True)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()