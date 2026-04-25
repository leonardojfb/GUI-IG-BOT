"""
🎨 INTERFAZ GRÁFICA INTUITIVA - ORGANIZADOR DE VIDEOS INSTAGRAM
Sistema VA Groups con Mezclas Cruzadas - Más intuitiva y con control total de mezclas
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import random
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(BASE_DIR, "videos_finales")
OUTPUT_ROOT = os.path.join(BASE_DIR, "CALENDARIO_POSTEO")
CONFIG_FILE = os.path.join(BASE_DIR, "organizer_config.json")

# ==================== CLASE PRINCIPAL ====================
class InstagramOrganizerSimple:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Organizador Instagram - Mezclas & VA")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e2e")
        
        self.config = self.load_config()
        self.create_widgets()
        
    def load_config(self):
        """Cargar configuración"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "va_groups": {},
            "video_types": {
                "suicide": {"name": "Suicide", "folder": "suicide", "color": "#ff6b6b"},
                "promo": {"name": "Promo", "folder": "promo", "color": "#4ecdc4"},
                "con_cara": {"name": "Con Cara", "folder": "con_cara", "color": "#ffe66d"}
            },
            "mixes": {}
        }
    
    def save_config(self):
        """Guardar configuración"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")
    
    def get_inventory(self):
        """Obtener inventario"""
        inventory = {}
        for vid_type, info in self.config["video_types"].items():
            folder = os.path.join(SOURCE_ROOT, info["folder"])
            if os.path.exists(folder):
                files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi'))]
                inventory[vid_type] = {"total": len(files), "files": sorted(files)}
            else:
                inventory[vid_type] = {"total": 0, "files": []}
        return inventory
    
    def create_widgets(self):
        """Crear interfaz intuitiva"""
        
        # ==================== HEADER ====================
        header = tk.Frame(self.root, bg="#2d2d44", height=70)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="🎬 ORGANIZADOR INSTAGRAM", 
                font=("Arial", 18, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        
        # ==================== PANEL PRINCIPAL ====================
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True)
        
        # ==================== SIDEBAR ====================
        sidebar = tk.Frame(main, bg="#2d2d44", width=250)
        main.add(sidebar, minsize=250)
        
        tk.Label(sidebar, text="👥 GRUPOS DE VA", font=("Arial", 12, "bold"), 
                bg="#2d2d44", fg="#4ecdc4").pack(pady=15)
        
        self.va_list = tk.Listbox(sidebar, bg="#1e1e2e", fg="white", font=("Arial", 11))
        self.va_list.pack(fill=tk.BOTH, expand=True, padx=10)
        self.va_list.bind('<<ListboxSelect>>', self.show_va_details)
        
        btn_frame = tk.Frame(sidebar, bg="#2d2d44")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="➕ Agregar", command=self.add_va,
                  bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 9)).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🗑️", command=self.delete_va,
                  bg="#ff6b6b", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=3)
        
        # ==================== CONTENIDO ====================
        content = tk.Frame(main, bg="#1e1e2e")
        main.add(content, minsize=700)
        
        # Notebook
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestañas
        self.tab_va = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_mix = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_video = tk.Frame(self.notebook, bg="#1e1e2e")
        
        self.notebook.add(self.tab_va, text="👤 Cuentas por VA")
        self.notebook.add(self.tab_mix, text="🔀 Mezclas Cruzadas")
        self.notebook.add(self.tab_video, text="🎞️ Tipos de Video")
        
        self.create_va_tab()
        self.create_mix_tab()
        self.create_video_tab()
        
        self.refresh_va_list()
    
    # ==================== VA TAB ====================
    def create_va_tab(self):
        """Pestaña de VA Groups"""
        main = tk.Frame(self.tab_va, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Info del VA seleccionado
        self.va_info_frame = tk.LabelFrame(main, text="👤 SELECCIONA UN GRUPO VA", 
                                            bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        self.va_info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.va_accounts_widgets = {}
        
        # Botón guardar
        tk.Button(main, text="💾 GUARDAR CAMBIOS", command=self.save_va_accounts,
                  bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 11, "bold")).pack(pady=10)
    
    def refresh_va_list(self):
        """Actualizar lista de VA"""
        self.va_list.delete(0, tk.END)
        for gid, gdata in self.config["va_groups"].items():
            total = sum(len(v) for v in gdata.get("accounts", {}).values())
            self.va_list.insert(tk.END, f"{gdata.get('name', gid)} ({total})")
    
    def show_va_details(self, event):
        """Mostrar detalles del VA seleccionado"""
        sel = self.va_list.curselection()
        if not sel:
            return
        
        va_name = self.va_list.get(sel[0]).split(" (")[0]
        
        # Buscar ID
        va_id = None
        for gid, gdata in self.config["va_groups"].items():
            if gdata.get("name") == va_name:
                va_id = gid
                break
        
        if not va_id:
            return
        
        # Limpiar frame
        for w in self.va_info_frame.winfo_children():
            w.destroy()
        
        tk.Label(self.va_info_frame, text=f"👤 {va_name}", font=("Arial", 14, "bold"),
                bg="#2d2d44", fg="#4ecdc4").pack(pady=10)
        
        self.va_accounts_widgets = {"va_id": va_id}
        
        # Crear entrada para cada tipo de video
        inv = self.get_inventory()
        
        for vid_type, info in self.config["video_types"].items():
            type_frame = tk.Frame(self.va_info_frame, bg="#2d2d44")
            type_frame.pack(fill=tk.X, padx=20, pady=10)
            
            # Label con color
            tk.Label(type_frame, text=f"● {info['name']}", font=("Arial", 11, "bold"),
                    bg="#2d2d44", fg=info["color"]).pack(anchor=tk.W)
            
            available = inv.get(vid_type, {}).get("total", 0)
            tk.Label(type_frame, text=f"   ({available} videos disponibles)", 
                    bg="#2d2d44", fg="#888", font=("Arial", 9)).pack(anchor=tk.W)
            
            # Entry para cuentas
            accounts_var = tk.StringVar()
            current = self.config["va_groups"][va_id].get("accounts", {}).get(vid_type, [])
            accounts_var.set(", ".join(current))
            
            entry = tk.Entry(type_frame, textvariable=accounts_var, width=60, bg="#1e1e2e", fg="white")
            entry.pack(pady=5)
            
            self.va_accounts_widgets[vid_type] = accounts_var
    
    def add_va(self):
        """Agregar VA Group"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nuevo Grupo VA")
        dialog.geometry("350x120")
        dialog.configure(bg="#2d2d44")
        
        tk.Label(dialog, text="Nombre del VA/Grupo:", bg="#2d2d44", fg="white").pack(pady=10)
        entry = tk.Entry(dialog, width=30)
        entry.pack(pady=10)
        
        def save():
            name = entry.get().strip()
            if name:
                vid = name.lower().replace(" ", "_")
                self.config["va_groups"][vid] = {"name": name, "accounts": {}}
                self.save_config()
                self.refresh_va_list()
                dialog.destroy()
        
        tk.Button(dialog, text="➕ Crear", command=save, bg="#4ecdc4", fg="#1e1e2e").pack(pady=10)
    
    def delete_va(self):
        """Eliminar VA Group"""
        sel = self.va_list.curselection()
        if not sel:
            messagebox.showwarning("⚠️", "Selecciona un grupo primero")
            return
        
        name = self.va_list.get(sel[0]).split(" (")[0]
        
        for gid, gdata in list(self.config["va_groups"].items()):
            if gdata.get("name") == name:
                if messagebox.askyesno("Confirmar", f"¿Eliminar '{name}'?"):
                    del self.config["va_groups"][gid]
                    self.save_config()
                    self.refresh_va_list()
                break
    
    def save_va_accounts(self):
        """Guardar cuentas del VA"""
        if "va_id" not in self.va_accounts_widgets:
            messagebox.showwarning("⚠️", "Selecciona un grupo VA primero")
            return
        
        va_id = self.va_accounts_widgets["va_id"]
        
        for vid_type in self.config["video_types"]:
            if vid_type in self.va_accounts_widgets:
                accounts_str = self.va_accounts_widgets[vid_type].get()
                accounts = [a.strip() for a in accounts_str.split(",") if a.strip()]
                
                if "accounts" not in self.config["va_groups"][va_id]:
                    self.config["va_groups"][va_id]["accounts"] = {}
                
                self.config["va_groups"][va_id]["accounts"][vid_type] = accounts
        
        self.save_config()
        self.refresh_va_list()
        messagebox.showinfo("✅", "Cuentas guardadas correctamente")
    
    # ==================== MEZCLAS TAB ====================
    def create_mix_tab(self):
        """Pestaña de Mezclas Cruzadas"""
        main = tk.Frame(self.tab_mix, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Crear mezcla
        create_frame = tk.LabelFrame(main, text="🔀 CREAR MEZCLA CRUZADA", 
                                      bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        create_frame.pack(fill=tk.X, pady=10)
        
        # Nombre
        name_frame = tk.Frame(create_frame, bg="#2d2d44")
        name_frame.pack(pady=15)
        
        tk.Label(name_frame, text="Nombre:", bg="#2d2d44", fg="white").pack(side=tk.LEFT)
        self.mix_name = tk.Entry(name_frame, width=25)
        self.mix_name.pack(side=tk.LEFT, padx=10)
        
        # Sección de mezcla cruzada
        mix_frame = tk.LabelFrame(main, text="🎬 QUÉ VIDEOS SE MEZCLAN CON QUÉ", 
                                  bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        mix_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        inv = self.get_inventory()
        
        # Para cada tipo de video, permitir seleccionar con qué otros tipos mezclarse
        self.mix_config = {}
        
        for target_type, target_info in self.config["video_types"].items():
            target_frame = tk.LabelFrame(mix_frame, 
                                        text=f"● {target_info['name']} se mezcla con:",
                                        bg="#2d2d44", fg=target_info["color"],
                                        font=("Arial", 10, "bold"))
            target_frame.pack(fill=tk.X, padx=10, pady=8)
            
            inner = tk.Frame(target_frame, bg="#2d2d44")
            inner.pack(pady=10)
            
            # Checkboxes para cada tipo fuente
            type_vars = {}
            type_counts = {}
            
            for source_type, source_info in self.config["video_types"].items():
                row = tk.Frame(inner, bg="#2d2d44")
                row.pack(fill=tk.X, pady=3)
                
                var = tk.BooleanVar(value=False)
                type_vars[source_type] = var
                
                tk.Checkbutton(row, text=f"  {source_info['name']}", variable=var,
                              bg="#2d2d44", fg=source_info["color"]).pack(side=tk.LEFT)
                
                available = inv.get(source_type, {}).get("total", 0)
                tk.Label(row, text=f"({available})", bg="#2d2d44", fg="#666", 
                        font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
                
                tk.Label(row, text="cant:", bg="#2d2d44", fg="white").pack(side=tk.LEFT, padx=(10, 3))
                count_entry = tk.Entry(row, width=5)
                count_entry.insert(0, "3")
                count_entry.pack(side=tk.LEFT)
                type_counts[source_type] = count_entry
            
            self.mix_config[target_type] = {
                "vars": type_vars,
                "counts": type_counts
            }
        
        # Opciones
        opt_frame = tk.Frame(create_frame, bg="#2d2d44")
        opt_frame.pack(pady=15)
        
        self.mix_random = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="Orden aleatorio", variable=self.mix_random,
                      bg="#2d2d44", fg="white").pack(side=tk.LEFT, padx=20)
        
        tk.Button(opt_frame, text="🎬 CREAR MEZCLA", command=self.create_cross_mix,
                  bg="#ff6b6b", fg="white", font=("Arial", 11, "bold"), padx=20).pack(side=tk.LEFT, padx=30)
        
        # Lista de mezclas
        list_frame = tk.LabelFrame(main, text="💾 MEZCLAS GUARDADAS", 
                                   bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.mixes_list = tk.Listbox(list_frame, bg="#1e1e2e", fg="white", height=10)
        self.mixes_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.refresh_mixes_list()
    
    def create_cross_mix(self):
        """Crear mezcla cruzada"""
        name = self.mix_name.get().strip()
        if not name:
            messagebox.showwarning("⚠️", "Ingresa un nombre para la mezcla")
            return
        
        inv = self.get_inventory()
        mix_result = {}
        
        # Recopilar videos por cada tipo objetivo
        for target_type in self.config["video_types"]:
            if target_type not in self.mix_config:
                continue
            
            config = self.mix_config[target_type]
            videos = []
            
            for source_type, var in config["vars"].items():
                if var.get():
                    try:
                        count = int(config["counts"][source_type].get() or 3)
                    except:
                        count = 3
                    
                    source_files = inv.get(source_type, {}).get("files", [])
                    for f in source_files[:count]:
                        videos.append({
                            "file": f,
                            "source_type": source_type,
                            "target_type": target_type
                        })
            
            if videos:
                if self.mix_random.get():
                    random.shuffle(videos)
                mix_result[target_type] = [v["file"] for v in videos]
        
        if not mix_result:
            messagebox.showwarning("⚠️", "Selecciona al menos una combinación")
            return
        
        # Guardar
        self.config["mixes"][name] = {
            "config": {t: {s: c.get() for s, c in zip(cfg["vars"].keys(), [cfg["vars"][s].get() for s in cfg["vars"]])} 
                      for t, cfg in self.mix_config.items()},
            "result": mix_result,
            "created": datetime.now().isoformat()
        }
        self.save_config()
        self.refresh_mixes_list()
        
        total = sum(len(v) for v in mix_result.values())
        messagebox.showinfo("✅", f"Mezcla '{name}' creada con {total} videos")
    
    def refresh_mixes_list(self):
        """Actualizar lista de mezclas"""
        self.mixes_list.delete(0, tk.END)
        for name, data in self.config["mixes"].items():
            total = sum(len(v) for v in data.get("result", {}).values())
            self.mixes_list.insert(tk.END, f"🔀 {name} ({total} videos)")
    
    # ==================== VIDEO TYPES TAB ====================
    def create_video_tab(self):
        """Pestaña de tipos de video"""
        main = tk.Frame(self.tab_video, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Lista
        list_frame = tk.LabelFrame(main, text="🎞️ TIPOS DE VIDEO CONFIGURADOS", 
                                   bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.video_types_list = tk.Listbox(list_frame, bg="#1e1e2e", fg="white", height=12)
        self.video_types_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = tk.Frame(list_frame, bg="#2d2d44")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="➕ Agregar Tipo", command=self.add_video_type,
                  bg="#4ecdc4", fg="#1e1e2e").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Eliminar", command=self.remove_video_type,
                  bg="#ff6b6b", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Info
        self.video_info = tk.LabelFrame(main, text="ℹ️ INFORMACIÓN", 
                                         bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        self.video_info.pack(fill=tk.X, pady=10)
        
        self.video_info_text = tk.Text(self.video_info, height=8, bg="#1e1e2e", fg="white")
        self.video_info_text.pack(fill=tk.X, padx=10, pady=10)
        
        self.video_types_list.bind('<<ListboxSelect>>', self.show_video_info)
        
        self.refresh_video_types()
    
    def refresh_video_types(self):
        """Actualizar tipos de video"""
        self.video_types_list.delete(0, tk.END)
        for vid_type, info in self.config["video_types"].items():
            inv = self.get_inventory()
            total = inv.get(vid_type, {}).get("total", 0)
            self.video_types_list.insert(tk.END, f"● {info['name']} ({total} videos)")
    
    def show_video_info(self, event):
        """Mostrar info del tipo de video"""
        sel = self.video_types_list.curselection()
        if not sel:
            return
        
        name = self.video_types_list.get(sel[0]).split(" (")[0].replace("● ", "")
        
        for vid_type, info in self.config["video_types"].items():
            if info["name"] == name:
                inv = self.get_inventory()
                files = inv.get(vid_type, {}).get("files", [])
                
                self.video_info_text.delete(1.0, tk.END)
                self.video_info_text.insert(tk.END, f"Nombre: {info['name']}\n")
                self.video_info_text.insert(tk.END, f"Carpeta: {info['folder']}\n")
                self.video_info_text.insert(tk.END, f"Color: {info['color']}\n")
                self.video_info_text.insert(tk.END, f"Videos: {len(files)}\n\n")
                self.video_info_text.insert(tk.END, "Archivos:\n")
                for f in files[:10]:
                    self.video_info_text.insert(tk.END, f"  • {f}\n")
                if len(files) > 10:
                    self.video_info_text.insert(tk.END, f"  ... y {len(files)-10} más\n")
                break
    
    def add_video_type(self):
        """Agregar tipo de video"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nuevo Tipo de Video")
        dialog.geometry("350x200")
        dialog.configure(bg="#2d2d44")
        
        fields = [("Nombre:", "nombre"), ("Carpeta:", "carpeta"), ("Color:", "color")]
        entries = {}
        
        for i, (label, key) in enumerate(fields):
            tk.Label(dialog, text=label, bg="#2d2d44", fg="white").grid(row=i, column=0, padx=10, pady=10, sticky=tk.W)
            entry = tk.Entry(dialog, width=25)
            entry.grid(row=i, column=1, padx=10, pady=10)
            entries[key] = entry
        
        entries["color"].insert(0, "#4ecdc4")
        
        def save():
            name = entries["nombre"].get().strip()
            folder = entries["carpeta"].get().strip() or name.lower().replace(" ", "_")
            color = entries["color"].get().strip() or "#4ecdc4"
            
            if name:
                key = name.lower().replace(" ", "_")
                self.config["video_types"][key] = {"name": name, "folder": folder, "color": color}
                self.save_config()
                self.refresh_video_types()
                dialog.destroy()
        
        tk.Button(dialog, text="💾 Guardar", command=save, bg="#4ecdc4", fg="#1e1e2e").grid(row=3, column=0, columnspan=2, pady=15)
    
    def remove_video_type(self):
        """Eliminar tipo de video"""
        sel = self.video_types_list.curselection()
        if not sel:
            messagebox.showwarning("⚠️", "Selecciona un tipo")
            return
        
        name = self.video_types_list.get(sel[0]).split(" (")[0].replace("● ", "")
        
        for key, info in list(self.config["video_types"].items()):
            if info["name"] == name:
                if messagebox.askyesno("Confirmar", f"¿Eliminar '{name}'?"):
                    del self.config["video_types"][key]
                    self.save_config()
                    self.refresh_video_types()
                break


# ==================== MAIN ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerSimple(root)
    root.mainloop()