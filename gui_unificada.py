"""
🎨 GUI UNIFICADA - ORGANIZADOR DE VIDEOS INSTAGRAM
Conectada 100% a SQLite + Multithreading para procesos largos
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json
import random
import threading
import subprocess
import queue
from datetime import datetime
from database import DatabaseManager

# ==================== CONFIGURACIÓN ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(BASE_DIR, "videos_finales")
OUTPUT_ROOT = os.path.join(BASE_DIR, "CALENDARIO_POSTEO")

# ==================== HILO DE TRABAJO ====================
class WorkerThread(threading.Thread):
    """Hilo de trabajo para procesos largos"""
    
    def __init__(self, callback, task_name, *args, **kwargs):
        super().__init__()
        self.callback = callback
        self.task_name = task_name
        self.args = args
        self.kwargs = kwargs
        self.daemon = True
        self.error = None
        
    def run(self):
        try:
            result = self.callback(*self.args, **self.kwargs)
            if self.callback:
                self.root.after(0, lambda: self.callback(True, result))
        except Exception as e:
            self.error = str(e)
            if self.callback:
                self.root.after(0, lambda: self.callback(False, self.error))


# ==================== CLASE PRINCIPAL ====================
class InstagramOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Organizador Instagram - SQL + Multithreading")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e2e")
        
        # Conexión a base de datos
        self.db = DatabaseManager()
        
        # Variables de control
        self.is_processing = False
        self.process_queue = queue.Queue()
        
        # Crear interfaz
        self.create_widgets()
        self.refresh_data()
        
    def create_widgets(self):
        """Crear interfaz"""
        
        # ==================== HEADER ====================
        header = tk.Frame(self.root, bg="#2d2d44", height=70)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="🎬 ORGANIZADOR INSTAGRAM - SQL", 
                font=("Arial", 18, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        
        # ==================== PANEL PRINCIPAL ====================
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True)
        
        # ==================== SIDEBAR ====================
        sidebar = tk.Frame(main, bg="#2d2d44", width=250)
        main.add(sidebar, minsize=250)
        
        tk.Label(sidebar, text="👥 CUENTAS", font=("Arial", 12, "bold"), 
                bg="#2d2d44", fg="#4ecdc4").pack(pady=15)
        
        # Notebook para cuentas
        self.accounts_notebook = ttk.Notebook(sidebar)
        self.accounts_notebook.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Pestañas de cuentas por tipo
        self.account_tabs = {}
        for account_type in ['PROMO', 'SUICIDE']:
            tab = tk.Frame(self.accounts_notebook, bg="#2d2d44")
            self.accounts_notebook.add(tab, text=account_type)
            self.account_tabs[account_type] = tab
            
            # Listbox
            listbox = tk.Listbox(tab, bg="#1e1e2e", fg="white", font=("Arial", 10))
            listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            setattr(self, f'list_{account_type.lower()}', listbox)
            
            # Botones
            btn_frame = tk.Frame(tab, bg="#2d2d44")
            btn_frame.pack(pady=5)
            
            tk.Button(btn_frame, text="➕", command=lambda t=account_type: self.add_account(t),
                      bg="#4ecdc4", fg="#1e1e2e", width=3).pack(side=tk.LEFT, padx=2)
            tk.Button(btn_frame, text="🗑️", command=lambda t=account_type: self.delete_account(t),
                      bg="#ff6b6b", fg="white", width=3).pack(side=tk.LEFT, padx=2)
        
        # ==================== CONTENIDO ====================
        content = tk.Frame(main, bg="#1e1e2e")
        main.add(content, minsize=700)
        
        # Notebook principal
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestañas
        self.tab_inventory = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_video_types = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_actions = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_stats = tk.Frame(self.notebook, bg="#1e1e2e")
        
        self.notebook.add(self.tab_inventory, text="📦 Inventario")
        self.notebook.add(self.tab_video_types, text="🎞️ Tipos de Video")
        self.notebook.add(self.tab_actions, text="⚡ Acciones")
        self.notebook.add(self.tab_stats, text="📈 Estadísticas")
        
        self.create_inventory_tab()
        self.create_video_types_tab()
        self.create_actions_tab()
        self.create_stats_tab()
    
    # ==================== INVENTORY TAB ====================
    def create_inventory_tab(self):
        """Pestaña de inventario"""
        main = tk.Frame(self.tab_inventory, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Frame de inventario
        inv_frame = tk.LabelFrame(main, text="📦 INVENTARIO DE VIDEOS", 
                                   bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        inv_frame.pack(fill=tk.BOTH, expand=True)
        
        self.inventory_text = tk.Text(inv_frame, height=20, bg="#1e1e2e", fg="white", font=("Courier", 10))
        self.inventory_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Botón actualizar
        tk.Button(main, text="🔄 ACTUALIZAR", command=self.refresh_inventory,
                  bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 11, "bold")).pack(pady=10)
    
    def refresh_inventory(self):
        """Actualizar inventario desde carpetas"""
        self.inventory_text.delete(1.0, tk.END)
        
        # Obtener tipos de video de la DB
        video_types = self.db.get_active_video_types()
        
        total_videos = 0
        for vt in video_types:
            folder = os.path.join(SOURCE_ROOT, vt['type_name'].lower())
            if os.path.exists(folder):
                files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi'))]
                count = len(files)
                total_videos += count
                
                self.inventory_text.insert(tk.END, f"\n📁 {vt['type_name']} ({vt['category']})\n")
                self.inventory_text.insert(tk.END, f"   Videos: {count}\n")
                
                # Mostrar algunos archivos
                for f in files[:5]:
                    self.inventory_text.insert(tk.END, f"   • {f}\n")
                if len(files) > 5:
                    self.inventory_text.insert(tk.END, f"   ... y {len(files)-5} más\n")
            else:
                self.inventory_text.insert(tk.END, f"\n📁 {vt['type_name']} ({vt['category']})\n")
                self.inventory_text.insert(tk.END, f"   (Carpeta no existe)\n")
        
        self.inventory_text.insert(tk.END, f"\n{'='*40}\n")
        self.inventory_text.insert(tk.END, f"TOTAL: {total_videos} videos\n")
    
    # ==================== VIDEO TYPES TAB ====================
    def create_video_types_tab(self):
        """Pestaña de tipos de video"""
        main = tk.Frame(self.tab_video_types, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Lista
        list_frame = tk.LabelFrame(main, text="🎞️ TIPOS DE VIDEO EN DB", 
                                   bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.video_types_list = tk.Listbox(list_frame, bg="#1e1e2e", fg="white", height=10)
        self.video_types_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = tk.Frame(list_frame, bg="#2d2d44")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="➕ Agregar Tipo", command=self.add_video_type_gui,
                  bg="#4ecdc4", fg="#1e1e2e").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Eliminar", command=self.remove_video_type_gui,
                  bg="#ff6b6b", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 Actualizar", command=self.refresh_video_types_list,
                  bg="#00d9ff", fg="#1e1e2e").pack(side=tk.LEFT, padx=5)
        
        self.refresh_video_types_list()
    
    def refresh_video_types_list(self):
        """Actualizar lista de tipos de video"""
        self.video_types_list.delete(0, tk.END)
        
        video_types = self.db.get_video_types()
        for vt in video_types:
            status = "✅" if vt.get('is_active', 1) else "❌"
            self.video_types_list.insert(tk.END, f"{status} {vt['type_name']} ({vt['category']})")
    
    def add_video_type_gui(self):
        """Agregar tipo de video desde GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nuevo Tipo de Video")
        dialog.geometry("350x200")
        dialog.configure(bg="#2d2d44")
        
        tk.Label(dialog, text="Nombre:", bg="#2d2d44", fg="white").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        entry_name = tk.Entry(dialog, width=25)
        entry_name.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Label(dialog, text="Categoría:", bg="#2d2d44", fg="white").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        entry_category = tk.Entry(dialog, width=25)
        entry_category.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(dialog, text="Descripción:", bg="#2d2d44", fg="white").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        entry_desc = tk.Entry(dialog, width=25)
        entry_desc.grid(row=2, column=1, padx=10, pady=10)
        
        def save():
            name = entry_name.get().strip()
            category = entry_category.get().strip().upper()
            desc = entry_desc.get().strip()
            
            if name and category:
                try:
                    self.db.add_video_type(name, category, desc)
                    self.refresh_video_types_list()
                    messagebox.showinfo("✅", f"Tipo '{name}' agregado")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
            else:
                messagebox.showwarning("⚠️", "Nombre y categoría son requeridos")
        
        tk.Button(dialog, text="💾 Guardar", command=save, bg="#4ecdc4", fg="#1e1e2e").grid(row=3, column=0, columnspan=2, pady=15)
    
    def remove_video_type_gui(self):
        """Eliminar tipo de video desde GUI"""
        sel = self.video_types_list.curselection()
        if not sel:
            messagebox.showwarning("⚠️", "Selecciona un tipo")
            return
        
        name = self.video_types_list.get(sel[0]).split(" ")[1]
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{name}'?"):
            try:
                self.db.delete_video_type(name)
                self.refresh_video_types_list()
                messagebox.showinfo("✅", f"Tipo '{name}' eliminado")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    # ==================== ACTIONS TAB ====================
    def create_actions_tab(self):
        """Pestaña de acciones"""
        main = tk.Frame(self.tab_actions, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Renderizar videos
        render_frame = tk.LabelFrame(main, text="🎬 RENDERIZAR VIDEOS (Multithreading)", 
                                      bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        render_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(render_frame, text="Este proceso se ejecuta en segundo plano sin bloquear la UI", 
                bg="#2d2d44", fg="#888").pack(pady=10)
        
        tk.Button(render_frame, text="🚀 INICIAR RENDERIZADO", command=self.start_render,
                  bg="#ff6b6b", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.render_progress = tk.Label(render_frame, text="", bg="#2d2d44", fg="#4ecdc4")
        self.render_progress.pack(pady=5)
        
        # Distribuir videos
        dist_frame = tk.LabelFrame(main, text="📅 DISTRIBUIR POR DÍAS", 
                                    bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        dist_frame.pack(fill=tk.X, pady=10)
        
        config_inner = tk.Frame(dist_frame, bg="#2d2d44")
        config_inner.pack(pady=10)
        
        tk.Label(config_inner, text="Videos por día:", bg="#2d2d44", fg="white").grid(row=0, column=0, padx=5)
        self.entry_daily_goal = tk.Entry(config_inner, width=10)
        self.entry_daily_goal.insert(0, "46")
        self.entry_daily_goal.grid(row=0, column=1, padx=5)
        
        tk.Button(config_inner, text="🚀 DISTRIBUIR", command=self.start_distribution,
                  bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 11, "bold")).grid(row=1, column=0, columnspan=2, pady=10)
        
        self.dist_progress = tk.Label(dist_frame, text="", bg="#2d2d44", fg="#4ecdc4")
        self.dist_progress.pack(pady=5)
        
        # Telegram
        telegram_frame = tk.LabelFrame(main, text="📱 ENVIAR A TELEGRAM (Multithreading)", 
                                        bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        telegram_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(telegram_frame, text="Envío en segundo plano sin bloquear la UI", 
                bg="#2d2d44", fg="#888").pack(pady=10)
        
        tk.Button(telegram_frame, text="📱 INICIAR ENVÍO", command=self.start_telegram,
                  bg="#00d9ff", fg="#1e1e2e", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.telegram_progress = tk.Label(telegram_frame, text="", bg="#2d2d44", fg="#00d9ff")
        self.telegram_progress.pack(pady=5)
    
    def start_render(self):
        """Iniciar renderizado en hilo separado"""
        if self.is_processing:
            messagebox.showwarning("⚠️", "Ya hay un proceso en ejecución")
            return
        
        self.is_processing = True
        self.render_progress.config(text="🔄 Renderizando en segundo plano...")
        
        # Ejecutar en hilo separado
        def render_task():
            try:
                import videos
                videos.run_render()
                return "Renderizado completado"
            except Exception as e:
                raise Exception(str(e))
        
        def on_complete(success, result):
            self.is_processing = False
            if success:
                self.render_progress.config(text="✅ " + result)
                messagebox.showinfo("✅", result)
            else:
                self.render_progress.config(text="❌ Error: " + result)
                messagebox.showerror("Error", result)
        
        thread = WorkerThread(on_complete, "Render", render_task)
        thread.start()
    
    def start_distribution(self):
        """Iniciar distribución en hilo separado"""
        if self.is_processing:
            messagebox.showwarning("⚠️", "Ya hay un proceso en ejecución")
            return
        
        try:
            daily_goal = int(self.entry_daily_goal.get())
        except:
            daily_goal = 46
        
        self.is_processing = True
        self.dist_progress.config(text="🔄 Distribuyendo en segundo plano...")
        
        def dist_task():
            try:
                import Organizador
                # Modificar temporalmente el goal
                Organizador.DAILY_GOAL = daily_goal
                Organizador.distribute()
                return "Distribución completada"
            except Exception as e:
                raise Exception(str(e))
        
        def on_complete(success, result):
            self.is_processing = False
            if success:
                self.dist_progress.config(text="✅ " + result)
                messagebox.showinfo("✅", result)
            else:
                self.dist_progress.config(text="❌ Error: " + result)
                messagebox.showerror("Error", result)
        
        thread = WorkerThread(on_complete, "Distribución", dist_task)
        thread.start()
    
    def start_telegram(self):
        """Iniciar envío a Telegram en hilo separado"""
        if self.is_processing:
            messagebox.showwarning("⚠️", "Ya hay un proceso en ejecución")
            return
        
        self.is_processing = True
        self.telegram_progress.config(text="🔄 Enviando a Telegram en segundo plano...")
        
        def telegram_task():
            # Simular envío a Telegram
            import time
            time.sleep(2)
            return "Envío a Telegram completado (simulado)"
        
        def on_complete(success, result):
            self.is_processing = False
            if success:
                self.telegram_progress.config(text="✅ " + result)
                messagebox.showinfo("✅", result)
            else:
                self.telegram_progress.config(text="❌ Error: " + result)
                messagebox.showerror("Error", result)
        
        thread = WorkerThread(on_complete, "Telegram", telegram_task)
        thread.start()
    
    # ==================== STATS TAB ====================
    def create_stats_tab(self):
        """Pestaña de estadísticas"""
        main = tk.Frame(self.tab_stats, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        stats_frame = tk.LabelFrame(main, text="📈 ESTADÍSTICAS DE LA BASE DE DATOS", 
                                     bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        self.stats_text = tk.Text(stats_frame, height=20, bg="#1e1e2e", fg="white", font=("Courier", 10))
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Button(main, text="🔄 ACTUALIZAR ESTADÍSTICAS", command=self.refresh_stats,
                  bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 11, "bold")).pack(pady=10)
        
        self.refresh_stats()
    
    def refresh_stats(self):
        """Actualizar estadísticas"""
        self.stats_text.delete(1.0, tk.END)
        
        # Estadísticas de cuentas
        stats = self.db.get_account_stats()
        
        self.stats_text.insert(tk.END, "="*50 + "\n")
        self.stats_text.insert(tk.END, "📊 ESTADÍSTICAS GENERALES\n")
        self.stats_text.insert(tk.END, "="*50 + "\n\n")
        
        self.stats_text.insert(tk.END, f"Total de cuentas: {stats['total_accounts']}\n")
        self.stats_text.insert(tk.END, f"Videos publicados: {stats['total_videos']}\n\n")
        
        self.stats_text.insert(tk.END, "Cuentas por tipo:\n")
        for t, c in stats.get('by_type', {}).items():
            self.stats_text.insert(tk.END, f"  • {t}: {c}\n")
        
        self.stats_text.insert(tk.END, "\nCuentas por estado:\n")
        for s, c in stats.get('by_status', {}).items():
            self.stats_text.insert(tk.END, f"  • {s}: {c}\n")
        
        # Tipos de video
        self.stats_text.insert(tk.END, "\n" + "="*50 + "\n")
        self.stats_text.insert(tk.END, "🎞️ TIPOS DE VIDEO\n")
        self.stats_text.insert(tk.END, "="*50 + "\n\n")
        
        video_types = self.db.get_video_types()
        for vt in video_types:
            status = "Activo" if vt.get('is_active', 1) else "Inactivo"
            self.stats_text.insert(tk.END, f"• {vt['type_name']} ({vt['category']}) - {status}\n")
            self.stats_text.insert(tk.END, f"  Descripción: {vt.get('description', '')}\n\n")
    
    # ==================== CUENTAS ====================
    def refresh_data(self):
        """Actualizar todos los datos"""
        self.refresh_accounts_list()
        self.refresh_inventory()
        self.refresh_video_types_list()
        self.refresh_stats()
    
    def refresh_accounts_list(self):
        """Actualizar lista de cuentas"""
        for account_type in ['PROMO', 'SUICIDE']:
            listbox = getattr(self, f'list_{account_type.lower()}')
            listbox.delete(0, tk.END)
            
            accounts = self.db.get_all_accounts(account_type)
            for acc in accounts:
                status = "🟢" if acc.get('status') == 'active' else "🔴"
                videos = acc.get('videos_posted', 0)
                listbox.insert(tk.END, f"{status} {acc['username']} ({videos} videos)")
    
    def add_account(self, account_type):
        """Agregar cuenta"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Nueva Cuenta {account_type}")
        dialog.geometry("300x120")
        dialog.configure(bg="#2d2d44")
        
        tk.Label(dialog, text="Username:", bg="#2d2d44", fg="white").pack(pady=10)
        entry = tk.Entry(dialog, width=30)
        entry.pack(pady=10)
        
        def save():
            username = entry.get().strip()
            if username:
                try:
                    self.db.add_virtual_account(username, account_type)
                    self.refresh_accounts_list()
                    messagebox.showinfo("✅", f"Cuenta '{username}' agregada")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        
        tk.Button(dialog, text="➕ Agregar", command=save, bg="#4ecdc4", fg="#1e1e2e").pack(pady=10)
    
    def delete_account(self, account_type):
        """Eliminar cuenta"""
        listbox = getattr(self, f'list_{account_type.lower()}')
        sel = listbox.curselection()
        
        if not sel:
            messagebox.showwarning("⚠️", "Selecciona una cuenta")
            return
        
        username = listbox.get(sel[0]).split(" ")[1]
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{username}'?"):
            try:
                self.db.delete_account(username)
                self.refresh_accounts_list()
                messagebox.showinfo("✅", f"Cuenta '{username}' eliminada")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def on_close(self):
        """Cerrar aplicación"""
        self.db.close()
        self.root.destroy()


# ==================== MAIN ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()