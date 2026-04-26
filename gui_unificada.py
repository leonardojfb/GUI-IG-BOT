"""
🎨 GUI UNIFICADA - V4 (Simplicidad y Flujo Lineal)
Basado en 4 pestañas operativas con Explorador de Archivos y Dashboard.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import random
from database import DatabaseManager

class InstagramOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Automatización Instagram SaaS")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e2e")
        self.db = DatabaseManager()
        
        # Estilos modernos para la tabla
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2d2d44", foreground="white", fieldbackground="#2d2d44", rowheight=25)
        style.map("Treeview", background=[("selected", "#4ecdc4")], foreground=[("selected", "#1e1e2e")])
        
        self.create_widgets()
        self.refresh_dashboard()

    def create_widgets(self):
        # HEADER
        header = tk.Frame(self.root, bg="#2d2d44", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="⚙️ PANEL DE CONTROL SAAS", font=("Arial", 16, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        
        # NOTEBOOK PRINCIPAL (4 PESTAÑAS)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tab_dash = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_team = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_mix = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_dist = tk.Frame(self.notebook, bg="#1e1e2e")
        
        self.notebook.add(self.tab_dash, text="📊 1. Dashboard (Vista General)")
        self.notebook.add(self.tab_team, text="👥 2. Equipo y Cuentas")
        self.notebook.add(self.tab_mix, text="🎬 3. Creador de Tandas (Clips)")
        self.notebook.add(self.tab_dist, text="🚀 4. Logística y Envíos")
        
        self.build_dashboard_tab()
        self.build_team_tab()
        self.build_mix_tab()
        self.build_dist_tab()

    # ==========================================
    # PESTAÑA 1: DASHBOARD
    # ==========================================
    def build_dashboard_tab(self):
        main = tk.Frame(self.tab_dash, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(main, text="Visión General de Cuentas y Asignaciones", font=("Arial", 12), bg="#1e1e2e", fg="#4ecdc4").pack(anchor="w", pady=5)
        
        # Tabla (Treeview)
        cols = ("VA", "Telegram ID", "Cuenta IG", "Tipo Contenido", "Videos Subidos")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=200, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Button(main, text="🔄 Actualizar Dashboard", command=self.refresh_dashboard, bg="#4ecdc4", fg="#1e1e2e").pack(pady=10)

    def refresh_dashboard(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Unir datos de VAs y Cuentas (Simulado con lógica de DB)
        accounts = self.db.get_all_accounts()
        vas = {va: self.get_va_tg_id(va) for va in self.db.get_vas()}
        
        # Ordenar por Tipo de Contenido para fácil lectura
        accounts.sort(key=lambda x: x.get('account_type', ''))
        
        for acc in accounts:
            va_name = acc.get('assigned_va', 'Sin Asignar')
            tg_id = vas.get(va_name, "N/A")
            self.tree.insert("", "end", values=(va_name, tg_id, f"@{acc['username']}", acc['account_type'], acc.get('videos_posted', 0)))

    def get_va_tg_id(self, va_name):
        # Función auxiliar para sacar el ID de Telegram
        cur = self.db.conn.cursor()
        cur.execute("SELECT tg_group_id FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        return row['tg_group_id'] if row and row['tg_group_id'] else "Sin TG"

    # ==========================================
    # PESTAÑA 2: EQUIPO Y CUENTAS
    # ==========================================
    def build_team_tab(self):
        main = tk.Frame(self.tab_team, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Mitad Izquierda (Crear VA)
        left = tk.Frame(main, bg="#2d2d44", width=350)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)
        
        tk.Label(left, text="1. Añadir Personal (VA)", font=("Arial", 12, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        tk.Label(left, text="Nombre:", bg="#2d2d44", fg="white").pack()
        self.e_va_name = tk.Entry(left, width=30); self.e_va_name.pack(pady=5)
        tk.Label(left, text="Chat ID Telegram:", bg="#2d2d44", fg="white").pack()
        self.e_va_tg = tk.Entry(left, width=30); self.e_va_tg.pack(pady=5)
        tk.Button(left, text="Guardar VA", bg="#4ecdc4", command=self.add_va_ui).pack(pady=10)
        
        self.list_vas = tk.Listbox(left, bg="#1e1e2e", fg="white", height=15)
        self.list_vas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mitad Derecha (Añadir Cuentas Bulk)
        right = tk.Frame(main, bg="#2d2d44")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(right, text="2. Añadir Cuentas IG (En Lote)", font=("Arial", 12, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        
        top_right = tk.Frame(right, bg="#2d2d44")
        top_right.pack(fill=tk.X, padx=15)
        
        tk.Label(top_right, text="Pegar cuentas (sin @, una por línea):", bg="#2d2d44", fg="white").pack(side=tk.LEFT)
        tk.Label(top_right, text="Tipo de Contenido (Ej. FITNESS):", bg="#2d2d44", fg="white").pack(side=tk.RIGHT, padx=40)
        
        mid_right = tk.Frame(right, bg="#2d2d44")
        mid_right.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.txt_accounts = tk.Text(mid_right, bg="#1e1e2e", fg="white", width=40)
        self.txt_accounts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ctrl_right = tk.Frame(mid_right, bg="#2d2d44", width=200)
        ctrl_right.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.e_acc_type = tk.Entry(ctrl_right, width=20); self.e_acc_type.pack(pady=10)
        tk.Button(ctrl_right, text="🚀 Añadir a la Base de Datos", bg="#ff6b6b", fg="white", command=self.add_bulk_accounts).pack(pady=10)
        
        # Asignación
        bot_right = tk.Frame(right, bg="#1e1e2e", height=100)
        bot_right.pack(fill=tk.X, side=tk.BOTTOM, pady=10, padx=15)
        tk.Label(bot_right, text="Para asignar VAs, selecciona cuentas en el Dashboard", bg="#1e1e2e", fg="#888").pack(pady=20)
        self.refresh_team_ui()

    def add_va_ui(self):
        n = self.e_va_name.get().strip()
        t = self.e_va_tg.get().strip()
        if n:
            self.db.add_va(n)
            if t: self.db.update_va_telegram_group(n, t)
            self.e_va_name.delete(0, tk.END)
            self.e_va_tg.delete(0, tk.END)
            self.refresh_team_ui()
            self.refresh_dashboard()

    def add_bulk_accounts(self):
        users = self.txt_accounts.get("1.0", tk.END).strip().split("\n")
        ctype = self.e_acc_type.get().strip().upper()
        if not ctype: return messagebox.showwarning("⚠️", "Define el Tipo de Contenido")
        
        for u in users:
            clean = u.strip().replace("@", "")
            if clean: self.db.add_virtual_account(clean, ctype)
        
        self.txt_accounts.delete("1.0", tk.END)
        self.refresh_dashboard()
        messagebox.showinfo("✅", f"Cuentas añadidas como {ctype}")

    def refresh_team_ui(self):
        self.list_vas.delete(0, tk.END)
        for va in self.db.get_vas(): self.list_vas.insert(tk.END, va)

    # ==========================================
    # PESTAÑA 3: CREADOR DE TANDAS (CLIPS)
    # ==========================================
    def build_mix_tab(self):
        main = tk.Frame(self.tab_mix, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Header Tanda
        top = tk.Frame(main, bg="#2d2d44")
        top.pack(fill=tk.X, pady=10)
        tk.Label(top, text="ID / Nombre de la Tanda (Ej: Lotes_Navidad):", bg="#2d2d44", fg="white", font=("Arial", 11)).pack(side=tk.LEFT, padx=10, pady=15)
        self.e_tanda_name = tk.Entry(top, width=40, font=("Arial", 11)); self.e_tanda_name.pack(side=tk.LEFT, padx=10)
        
        # Pantalla Dividida
        split = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg="#1e1e2e")
        split.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # P1 (Primero)
        p1_frame = tk.LabelFrame(split, text="1️⃣ Clips de Inicio (Fondos/P1)", bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        split.add(p1_frame, minsize=400)
        tk.Button(p1_frame, text="📂 Buscar Carpeta P1", command=lambda: self.pick_folder(1), bg="#4ecdc4").pack(pady=10)
        self.lbl_p1_path = tk.Label(p1_frame, text="Ruta: Ninguna", bg="#2d2d44", fg="#aaa"); self.lbl_p1_path.pack()
        self.list_p1 = tk.Listbox(p1_frame, bg="#1e1e2e", fg="white"); self.list_p1.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # P2 (Último)
        p2_frame = tk.LabelFrame(split, text="2️⃣ Clips de Final (Ganchos/P2)", bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        split.add(p2_frame, minsize=400)
        tk.Button(p2_frame, text="📂 Buscar Carpeta P2", command=lambda: self.pick_folder(2), bg="#4ecdc4").pack(pady=10)
        self.lbl_p2_path = tk.Label(p2_frame, text="Ruta: Ninguna", bg="#2d2d44", fg="#aaa"); self.lbl_p2_path.pack()
        self.list_p2 = tk.Listbox(p2_frame, bg="#1e1e2e", fg="white"); self.list_p2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Bottom (Captions & Procesar)
        bot = tk.Frame(main, bg="#2d2d44")
        bot.pack(fill=tk.X, pady=10)
        
        tk.Button(bot, text="📄 Archivo de Captions (.txt)", command=self.pick_captions, bg="#ff6b6b", fg="white").pack(side=tk.LEFT, padx=10, pady=15)
        self.lbl_cap_path = tk.Label(bot, text="Sin seleccionar", bg="#2d2d44", fg="white"); self.lbl_cap_path.pack(side=tk.LEFT)
        
        tk.Button(bot, text="⚙️ INICIAR MEZCLA DE TANDA", command=self.process_tanda, bg="#00d9ff", font=("Arial", 12, "bold")).pack(side=tk.RIGHT, padx=20)
        
        self.p1_dir = ""
        self.p2_dir = ""
        self.cap_file = ""

    def pick_folder(self, pane):
        folder = filedialog.askdirectory(title=f"Selecciona la carpeta para P{pane}")
        if not folder: return
        
        files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov'))]
        lbl = getattr(self, f"lbl_p{pane}_path")
        lst = getattr(self, f"list_p{pane}")
        
        lbl.config(text=f"Ruta: {folder} ({len(files)} videos)")
        lst.delete(0, tk.END)
        for f in files: lst.insert(tk.END, f)
        
        if pane == 1: self.p1_dir = folder
        else: self.p2_dir = folder

    def pick_captions(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            self.cap_file = file
            self.lbl_cap_path.config(text=os.path.basename(file))

    def process_tanda(self):
        tanda_name = self.e_tanda_name.get().strip().upper()
        if not tanda_name or not self.p1_dir or not self.p2_dir or not self.cap_file:
            return messagebox.showwarning("Faltan Datos", "Asegúrate de poner un Nombre, seleccionar P1, P2 y Captions.")
        
        # Aquí se conectaría tu FFmpeg pasándole self.p1_dir, self.p2_dir y tanda_name
        # También se guardaría la ruta del caption para esa tanda en la DB.
        messagebox.showinfo("Procesando", f"Simulando inicio de render para la tanda: {tanda_name}\nSe procesará en segundo plano.")

    # ==========================================
    # PESTAÑA 4: LOGÍSTICA Y ENVÍOS
    # ==========================================
    def build_dist_tab(self):
        main = tk.Frame(self.tab_dist, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        f1 = tk.LabelFrame(main, text="Opciones de Envío", bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        f1.pack(fill=tk.X, pady=10)
        
        tk.Label(f1, text="Tanda a Distribuir:", bg="#2d2d44", fg="white").grid(row=0, column=0, padx=10, pady=15)
        self.c_tandas = ttk.Combobox(f1, values=["Lanzamiento_Verano_Fit", "Memes_Random_1"]) # Simulado desde DB
        self.c_tandas.grid(row=0, column=1)
        
        tk.Label(f1, text="Tipo de Cuentas Destino:", bg="#2d2d44", fg="white").grid(row=0, column=2, padx=10)
        self.c_dest = ttk.Combobox(f1, values=["FITNESS", "PROMO"]) # Simulado
        self.c_dest.grid(row=0, column=3)
        
        tk.Label(f1, text="Videos por Día:", bg="#2d2d44", fg="white").grid(row=1, column=0, padx=10, pady=15)
        self.e_quota = tk.Entry(f1, width=10); self.e_quota.insert(0, "4"); self.e_quota.grid(row=1, column=1, sticky="w")
        
        self.fillup_var = tk.BooleanVar()
        tk.Checkbutton(f1, text="Habilitar 'Fill-up' (Rellena cuota re-mezclando clips viejos sin repetir el P1+P2 exacto)", 
                       variable=self.fillup_var, bg="#2d2d44", fg="#4ecdc4", selectcolor="#1e1e2e").grid(row=1, column=2, columnspan=2, sticky="w")
        
        tk.Button(main, text="🚀 DISTRIBUIR Y ENVIAR A TELEGRAM", bg="#ff6b6b", fg="white", font=("Arial", 14, "bold"), pady=10).pack(pady=30)

if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    root.mainloop()