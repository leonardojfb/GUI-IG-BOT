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
        cols = ("VA", "Telegram ID", "Cuenta IG", "Tipo Contenido", "Videos Subidos", "Fecha Agregado")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c, command=lambda col=c: self.treeview_sort_column(self.tree, col, False))
            self.tree.column(c, width=200, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Botonera de Acciones
        btn_frame = tk.Frame(main, bg="#1e1e2e")
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="📁 Cambiar Categoría", bg="#ff6b6b", fg="white", 
                  command=self.change_account_category).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="👤 Reasignar VA", bg="#00d9ff", fg="white", 
                  command=self.reassign_va).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ Eliminar Cuenta", bg="#ff4757", fg="white", 
                  command=self.delete_account).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 Actualizar", bg="#4ecdc4", fg="#1e1e2e", 
                  command=self.refresh_dashboard).pack(side=tk.LEFT, padx=5)

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
            # Extraer y formatear la fecha
            created_at = acc.get('created_at', 'N/A')
            if created_at != 'N/A' and created_at:
                # Intentar formatear la fecha (suponiendo formato ISO)
                try:
                    from datetime import datetime
                    fecha_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    fecha_formatted = fecha_dt.strftime('%d/%m/%Y')
                except:
                    fecha_formatted = str(created_at)[:10] if len(str(created_at)) >= 10 else str(created_at)
            else:
                fecha_formatted = 'N/A'
            self.tree.insert("", "end", values=(va_name, tg_id, f"@{acc['username']}", acc['account_type'], acc.get('videos_posted', 0), fecha_formatted))
    def get_va_tg_id(self, va_name):
        # Función auxiliar para sacar el ID de Telegram
        cur = self.db.conn.cursor()
        cur.execute("SELECT tg_group_id FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        return row['tg_group_id'] if row and row['tg_group_id'] else "Sin TG"
    def treeview_sort_column(self, tv, col, reverse):
        # Obtener todos los elementos
        items = []
        for child in tv.get_children(''):
            values = tv.item(child, 'values')
            # Encontrar el índice de la columna
            cols = tv.cget('columns')
            if isinstance(cols, tuple):
                col_idx = list(cols).index(col)
            else:
                col_idx = 0
            items.append((child, values, values[col_idx] if col_idx < len(values) else ''))
        
        # Ordenar los elementos (manejar números y texto)
        def sort_key(item):
            val = item[2]
            # Intentar convertir a número para ordenamiento numérico
            try:
                return (0, float(val))
            except (ValueError, TypeError):
                return (1, str(val).lower())
        
        items.sort(key=sort_key, reverse=reverse)
        
        # Reordenar los items en el Treeview
        for i, (child, values, _) in enumerate(items):
            tv.move(child, '', i)
        
        # Actualizar el comando del encabezado para invertir el orden
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    # ==========================================
    # MÉTODOS DE ACCIÓN DEL DASHBOARD
    # ==========================================
    def get_selected_account(self):
        """Obtiene la cuenta seleccionada en el Treeview"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("⚠️", "Selecciona una cuenta de la tabla primero.")
            return None
        item = self.tree.item(selection[0])
        values = item['values']
        # values[2] es la cuenta IG con formato "@username"
        username = values[2].lstrip('@')
        return username
    
    def change_account_category(self):
        """Cambia la categoría de la cuenta seleccionada"""
        username = self.get_selected_account()
        if not username:
            return
        
        # Obtener categorías disponibles
        categorias = self.db.get_categories()
        if not categorias:
            messagebox.showwarning("⚠️", "No hay categorías disponibles.")
            return
        
        # Crear diálogo simple
        dialog = tk.Toplevel(self.root)
        dialog.title("Cambiar Categoría")
        dialog.geometry("300x150")
        dialog.configure(bg="#2d2d44")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"Cambiar categoría de: @{username}", bg="#2d2d44", fg="white").pack(pady=10)
        tk.Label(dialog, text="Nueva Categoría:", bg="#2d2d44", fg="white").pack()
        
        combo = ttk.Combobox(dialog, values=categorias, state="readonly")
        combo.pack(pady=10)
        combo.focus()
        
        def guardar():
            nueva_cat = combo.get()
            if nueva_cat:
                try:
                    self.db.update_account(username, account_type=nueva_cat)
                    messagebox.showinfo("✅", f"Categoría de @{username} cambiada a {nueva_cat}")
                    dialog.destroy()
                    self.refresh_dashboard()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        
        tk.Button(dialog, text="Guardar", bg="#4ecdc4", command=guardar).pack(pady=10)
    
    def reassign_va(self):
        """Reasigna el VA de la cuenta seleccionada"""
        username = self.get_selected_account()
        if not username:
            return
        
        # Obtener VAs disponibles
        vas = self.db.get_vas()
        if not vas:
            messagebox.showwarning("⚠️", "No hay VAs disponibles. Añade primero un VA en la pestaña Equipo.")
            return
        
        # Crear diálogo simple
        dialog = tk.Toplevel(self.root)
        dialog.title("Reasignar VA")
        dialog.geometry("300x150")
        dialog.configure(bg="#2d2d44")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"Reasignar VA de: @{username}", bg="#2d2d44", fg="white").pack(pady=10)
        tk.Label(dialog, text="Nuevo VA:", bg="#2d2d44", fg="white").pack()
        
        combo = ttk.Combobox(dialog, values=vas, state="readonly")
        combo.pack(pady=10)
        combo.focus()
        
        def guardar():
            nuevo_va = combo.get()
            if nuevo_va:
                try:
                    self.db.update_account(username, assigned_va=nuevo_va)
                    messagebox.showinfo("✅", f"@{username} asignado a {nuevo_va}")
                    dialog.destroy()
                    self.refresh_dashboard()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        
        tk.Button(dialog, text="Guardar", bg="#4ecdc4", command=guardar).pack(pady=10)
    
    def delete_account(self):
        """Elimina la cuenta seleccionada"""
        username = self.get_selected_account()
        if not username:
            return
        
        respuesta = messagebox.askyesno(
            "⚠️ Confirmar Eliminación",
            f"¿Estás seguro de que quieres eliminar la cuenta @{username}?\n\nEsta acción no se puede deshacer."
        )
        
        if respuesta:
            try:
                self.db.delete_account(username)
                messagebox.showinfo("✅", f"Cuenta @{username} eliminada.")
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ==========================================
    # PESTAÑA 2: EQUIPO Y CUENTAS
    # ==========================================
    def build_team_tab(self):
        main = tk.Frame(self.tab_team, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Mitad Izquierda (Crear VA y Lista)
        left = tk.Frame(main, bg="#2d2d44", width=350)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)
        
        tk.Label(left, text="1. Añadir Personal (VA)", font=("Arial", 12, "bold"), bg="#2d2d44", fg="white").pack(pady=15)
        tk.Label(left, text="Nombre:", bg="#2d2d44", fg="white").pack()
        self.e_va_name = tk.Entry(left, width=30); self.e_va_name.pack(pady=5)
        tk.Label(left, text="Chat ID Telegram (Opcional):", bg="#2d2d44", fg="white").pack()
        self.e_va_tg = tk.Entry(left, width=30); self.e_va_tg.pack(pady=5)
        tk.Button(left, text="Guardar VA", bg="#4ecdc4", command=self.add_va_ui).pack(pady=10)
        
        tk.Label(left, text="Lista de VAs:", bg="#2d2d44", fg="white").pack(pady=5)
        # exportselection=False permite seleccionar aquí y en la otra lista sin que se desmarque
        self.list_vas = tk.Listbox(left, bg="#1e1e2e", fg="white", height=15, exportselection=False)
        self.list_vas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mitad Derecha (Añadir Cuentas y Asignar)
        right = tk.Frame(main, bg="#2d2d44")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Superior Derecha (Añadir Cuentas)
        top_right = tk.Frame(right, bg="#2d2d44")
        top_right.pack(fill=tk.X, padx=15, pady=10)
        
        tk.Label(top_right, text="2. Añadir Cuentas IG (En Lote)", font=("Arial", 12, "bold"), bg="#2d2d44", fg="white").pack(anchor="w")
        
        input_frame = tk.Frame(top_right, bg="#2d2d44")
        input_frame.pack(fill=tk.X, pady=5)
        
        self.txt_accounts = tk.Text(input_frame, bg="#1e1e2e", fg="white", height=4, width=40)
        self.txt_accounts.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ctrl_frame = tk.Frame(input_frame, bg="#2d2d44")
        ctrl_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(ctrl_frame, text="Tipo de Contenido (Ej. FITNESS):", bg="#2d2d44", fg="white").pack()
        self.e_acc_type = tk.Entry(ctrl_frame, width=20); self.e_acc_type.pack(pady=5)
        tk.Button(ctrl_frame, text="🚀 Añadir a DB", bg="#ff6b6b", fg="white", command=self.add_bulk_accounts).pack()
        
        # Inferior Derecha (Módulo de Asignación)
        bot_right = tk.Frame(right, bg="#1e1e2e")
        bot_right.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        tk.Label(bot_right, text="3. Módulo de Asignación", font=("Arial", 12, "bold"), bg="#1e1e2e", fg="white").pack(anchor="w", pady=(10, 0), padx=10)
        tk.Label(bot_right, text="Paso A: Selecciona un VA a la izquierda. Paso B: Selecciona cuentas aquí abajo. Paso C: Clic en Asignar.", bg="#1e1e2e", fg="#aaa").pack(anchor="w", padx=10)
        
        self.list_accs = tk.Listbox(bot_right, bg="#2d2d44", fg="white", selectmode=tk.EXTENDED, exportselection=False)
        self.list_accs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Button(bot_right, text="🔗 ASIGNAR VA A CUENTAS SELECCIONADAS", bg="#00d9ff", font=("Arial", 11, "bold"), command=self.assign_va_to_accounts).pack(pady=10)
        
        self.refresh_team_ui()
    def add_category_ui(self):
        name = filedialog.simpledialog.askstring("Nueva Categoría", "Nombre (Ej: MODELOS, GAMING):")
        if name:
            self.db.add_category(name.strip().upper())
            messagebox.showinfo("✅", f"Categoría '{name}' creada.")
            self.refresh_dashboard() # Para que aparezca en los filtros
    def add_va_ui(self):
        n = self.e_va_name.get().strip()
        t = self.e_va_tg.get().strip()
        if n:
            try:
                self.db.add_va(n)
                if t: self.db.update_va_telegram_group(n, t)
                self.e_va_name.delete(0, tk.END)
                self.e_va_tg.delete(0, tk.END)
                self.refresh_team_ui()
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el VA: {e}")

    def add_bulk_accounts(self):
        users = self.txt_accounts.get("1.0", tk.END).strip().split("\n")
        ctype = self.e_acc_type.get().strip().upper()
        if not ctype: return messagebox.showwarning("⚠️", "Define el Tipo de Contenido")
        
        added = 0
        errores = 0
        for u in users:
            clean = u.strip().replace("@", "")
            if clean: 
                try:
                    self.db.add_virtual_account(clean, ctype)
                    added += 1
                except Exception:
                    errores += 1  # Ignora las repetidas silenciosamente
        
        self.txt_accounts.delete("1.0", tk.END)
        self.refresh_dashboard()
        self.refresh_team_ui() # Actualiza la lista de abajo al instante
        
        if added > 0:
            msg = f"✅ Se añadieron {added} cuentas."
            if errores > 0: msg += f" Se omitieron {errores} (repetidas)."
            messagebox.showinfo("Completado", msg)
        elif errores > 0:
            messagebox.showwarning("Atención", "Todas las cuentas ya existían en la base de datos.")

    def refresh_team_ui(self):
        self.list_vas.delete(0, tk.END)
        for va in self.db.get_vas(): 
            self.list_vas.insert(tk.END, va)
            
        self.list_accs.delete(0, tk.END)
        for acc in self.db.get_all_accounts():
            va_assigned = acc.get('assigned_va', 'Sin Asignar')
            self.list_accs.insert(tk.END, f"[{acc['id']}] @{acc['username']} | Tipo: {acc['account_type']} | VA: {va_assigned}")

    def assign_va_to_accounts(self):
        sel_va = self.list_vas.curselection()
        sel_accs = self.list_accs.curselection()
        
        if not sel_va:
            return messagebox.showwarning("⚠️", "Selecciona un VA de la lista de la izquierda.")
        if not sel_accs:
            return messagebox.showwarning("⚠️", "Selecciona al menos una cuenta de la lista de abajo.")
            
        va_name = self.list_vas.get(sel_va[0])
        
        account_ids = []
        for i in sel_accs:
            texto = self.list_accs.get(i)
            # Extrae el ID de la base de datos que está entre corchetes [ID]
            acc_id = int(texto.split("]")[0].replace("[", ""))
            account_ids.append(acc_id)
            
        # Bulk update en la BD
        try:
            self.db.bulk_update_accounts(account_ids, assigned_va=va_name)
            self.refresh_team_ui()
            self.refresh_dashboard()
            messagebox.showinfo("✅", f"Se asignaron {len(account_ids)} cuentas al VA: {va_name}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
        
        # 1. Cargar Tandas dinámicamente desde la BD
        # Usamos un try/except por si la IA de VS Code aún no ha creado la función en database.py
        try:
            tandas_data = self.db.get_all_tandas()
            lista_tandas = [t['tanda_name'] for t in tandas_data]
        except Exception:
            lista_tandas = [] 
            
        tk.Label(f1, text="Tanda a Distribuir:", bg="#2d2d44", fg="white").grid(row=0, column=0, padx=10, pady=15)
        self.c_tandas = ttk.Combobox(f1, values=lista_tandas)
        self.c_tandas.grid(row=0, column=1)
        
        # 2. Cargar Categorías Destino dinámicamente desde la BD
        categorias = self.db.get_categories()
        tk.Label(f1, text="Tipo de Cuentas Destino:", bg="#2d2d44", fg="white").grid(row=0, column=2, padx=10)
        self.c_dest = ttk.Combobox(f1, values=categorias)
        self.c_dest.grid(row=0, column=3)
        
        # 3. Cuota diaria y Fill-up
        tk.Label(f1, text="Videos por Día:", bg="#2d2d44", fg="white").grid(row=1, column=0, padx=10, pady=15)
        self.e_quota = tk.Entry(f1, width=10)
        self.e_quota.insert(0, "4")
        self.e_quota.grid(row=1, column=1, sticky="w")
        
        self.fillup_var = tk.BooleanVar()
        tk.Checkbutton(f1, text="Habilitar 'Fill-up' (Rellena cuota re-mezclando clips viejos sin repetir el P1+P2 exacto)", 
                       variable=self.fillup_var, bg="#2d2d44", fg="#4ecdc4", selectcolor="#1e1e2e").grid(row=1, column=2, columnspan=2, sticky="w")
        
        tk.Button(main, text="🚀 DISTRIBUIR Y ENVIAR A TELEGRAM", bg="#ff6b6b", fg="white", font=("Arial", 14, "bold"), pady=10).pack(pady=30)

if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    root.mainloop()