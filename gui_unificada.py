"""
🎨 GUI UNIFICADA - V6 (Código Expandido y Estructurado)
Gestión Total, Limpieza Masiva y Anti-Choque Global.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import threading
import Organizador
from database import DatabaseManager

# ==========================================
# GESTIÓN DE HILOS (Para procesos pesados)
# ==========================================
class WorkerThread(threading.Thread):
    def __init__(self, root, callback, task, *args, **kwargs):
        super().__init__()
        self.root = root
        self.callback = callback
        self.task = task
        self.args = args
        self.kwargs = kwargs
        self.daemon = True
        
    def run(self):
        try:
            res = self.task(*self.args, **self.kwargs)
            if self.callback: 
                # Congelamos el resultado en la variable 'r'
                self.root.after(0, lambda r=res: self.callback(True, r))
        except Exception as e:
            # Capturamos el texto exacto antes de que Python destruya el objeto 'e'
            error_msg = str(e)
            if self.callback: 
                # Congelamos el mensaje de error en la variable 'm'
                self.root.after(0, lambda m=error_msg: self.callback(False, m))
# ==========================================
# DIÁLOGO DE SELECCIÓN INTELIGENTE
# ==========================================
class SelectionDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, items):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x250")
        self.configure(bg="#2d2d44")
        self.result = None
        self.transient(parent)
        self.grab_set()

        lbl_prompt = tk.Label(self, text=prompt, bg="#2d2d44", fg="white", font=("Arial", 10, "bold"))
        lbl_prompt.pack(pady=10)
        
        lbl_combo = tk.Label(self, text="Selecciona existente:", bg="#2d2d44", fg="#aaa")
        lbl_combo.pack()
        
        self.combo = ttk.Combobox(self, values=items, state="readonly")
        self.combo.pack(pady=5, padx=20, fill=tk.X)
        
        lbl_entry = tk.Label(self, text="O escribe uno nuevo:", bg="#2d2d44", fg="#aaa")
        lbl_entry.pack(pady=(10,0))
        
        self.entry = tk.Entry(self)
        self.entry.pack(pady=5, padx=20, fill=tk.X)

        btn_frame = tk.Frame(self, bg="#2d2d44")
        btn_frame.pack(pady=20)
        
        btn_apply = tk.Button(btn_frame, text="✅ Aplicar", bg="#4ecdc4", width=10, command=self.confirm)
        btn_apply.pack(side=tk.LEFT, padx=5)
        
        btn_cancel = tk.Button(btn_frame, text="❌ Cancelar", bg="#ff4757", width=10, command=self.destroy)
        btn_cancel.pack(side=tk.LEFT)

    def confirm(self):
        new_val = self.entry.get().strip()
        selected_val = self.combo.get()
        self.result = new_val if new_val else selected_val
        
        if self.result: 
            self.destroy()
        else: 
            messagebox.showwarning("⚠️", "Selecciona o escribe algo.")

# ==========================================
# VENTANA DE GESTIÓN DE LISTAS (LIMPIEZA)
# ==========================================
class ListManager(tk.Toplevel):
    def __init__(self, parent, db, type_mode):
        super().__init__(parent)
        self.db = db
        self.type_mode = type_mode 
        self.title(f"Gestionar {type_mode}")
        self.geometry("400x500")
        self.configure(bg="#1e1e2e")
        
        lbl_title = tk.Label(self, text=f"Lista de {type_mode}", font=("Arial", 12, "bold"), bg="#1e1e2e", fg="white")
        lbl_title.pack(pady=10)
        
        self.listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, bg="#2d2d44", fg="white", font=("Arial", 11))
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        btn_select_all = tk.Button(btn_frame, text="Seleccionar Todo", bg="#4ecdc4", command=lambda: self.listbox.select_set(0, tk.END))
        btn_select_all.pack(side=tk.LEFT, padx=5)
        
        btn_delete = tk.Button(btn_frame, text="🗑️ Borrar Seleccionados", bg="#ff4757", fg="white", command=self.delete_selected)
        btn_delete.pack(side=tk.RIGHT)
        
        self.load_items()

    def load_items(self):
        self.listbox.delete(0, tk.END)
        if self.type_mode == "CATEGORIAS":
            items = self.db.get_categories()
        else:
            items = self.db.get_vas()
            
        for item in items: 
            self.listbox.insert(tk.END, item)

    def delete_selected(self):
        selected_indices = self.listbox.curselection()
        selected_items = [self.listbox.get(i) for i in selected_indices]
        
        if not selected_items: 
            return
            
        if messagebox.askyesno("Confirmar", f"¿Borrar {len(selected_items)} elementos? Esto no eliminará las cuentas, solo las opciones de la lista."):
            for item in selected_items:
                if self.type_mode == "CATEGORIAS": 
                    self.db.delete_category(item)
                else: 
                    self.db.delete_va(item)
            self.load_items()
            messagebox.showinfo("✅", "Limpieza completada.")
class AccountManager(tk.Toplevel):
    def __init__(self, parent, db, refresh_callback):
        super().__init__(parent)
        self.db = db
        self.refresh_callback = refresh_callback
        self.title("Gestionar Cuentas (Edición Masiva)")
        self.geometry("500x600")
        self.configure(bg="#1e1e2e")
        
        tk.Label(self, text="Selecciona las cuentas a mover:", font=("Arial", 12, "bold"), bg="#1e1e2e", fg="white").pack(pady=10)
        
        # Lista con selección múltiple
        self.listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, bg="#2d2d44", fg="white", font=("Arial", 11))
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Frame para la acción de mover
        action_frame = tk.LabelFrame(self, text="⚡ Acción Masiva", bg="#2d2d44", fg="#4ecdc4", font=("Arial", 10, "bold"))
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(action_frame, text="Mover a:", bg="#2d2d44", fg="white").pack(side=tk.LEFT, padx=10, pady=10)
        
        self.combo_cat = ttk.Combobox(action_frame, values=self.db.get_categories(), state="readonly")
        self.combo_cat.pack(side=tk.LEFT, padx=10, pady=10)
        
        btn_move = tk.Button(action_frame, text="Asignar Categoría", bg="#ff6b6b", fg="white", command=self.apply_bulk_change)
        btn_move.pack(side=tk.RIGHT, padx=10, pady=10)
        
        self.load_accounts()

    def load_accounts(self):
        self.listbox.delete(0, tk.END)
        self.account_data = self.db.get_all_accounts() # Usa tu método real
        for acc in self.account_data:
            # Mostramos el usuario y su categoría actual
            self.listbox.insert(tk.END, f"@{acc['username']} ({acc['account_type']})")

    def apply_bulk_change(self):
        selected_indices = self.listbox.curselection()
        new_cat = self.combo_cat.get()
        
        if not selected_indices:
            return messagebox.showwarning("⚠️", "Selecciona al menos una cuenta.")
        if not new_cat:
            return messagebox.showwarning("⚠️", "Elige una categoría de destino.")
            
        # Extraer los IDs de las cuentas seleccionadas
        ids_to_update = [self.account_data[i]['id'] for i in selected_indices]
        
        if messagebox.askyesno("Confirmar", f"¿Mover {len(ids_to_update)} cuentas a {new_cat}?"):
            # Llama a tu método bulk_update_accounts en database.py
            # Nota: usamos account_type porque así se llama en tu tabla virtual_accounts
            self.db.bulk_update_accounts(ids_to_update, account_type=new_cat)
            
            messagebox.showinfo("✅", "Cambio masivo completado.")
            self.refresh_callback() # Esto actualiza el Dashboard automáticamente
            self.load_accounts() # Refresca esta ventanita
# ==========================================
# CLASE PRINCIPAL DE LA APLICACIÓN
# ==========================================
class InstagramOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Automatización Instagram SaaS")
        self.root.geometry("1250x850")
        self.root.configure(bg="#1e1e2e")
        self.db = DatabaseManager()
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2d2d44", foreground="white", fieldbackground="#2d2d44", rowheight=25)
        style.map("Treeview", background=[("selected", "#4ecdc4")], foreground=[("selected", "#1e1e2e")])
        
        # Variables de rutas
        self.p1_dir = ""
        self.p2_dir = ""
        self.cap_file = ""
        
        self.create_widgets()
        self.refresh_dashboard()
    def apply_bulk_category(self):
        """Ejecuta el cambio masivo y refresca todo el ecosistema."""
        new_cat = self.c_bulk_cat.get()
        if not new_cat:
            return messagebox.showwarning("⚠️", "Selecciona una categoría de destino primero.")
        
        pregunta = f"¿Estás seguro de que quieres mover TODAS las cuentas a la categoría '{new_cat}'?\nEsto afectará la distribución y el dashboard inmediatamente."
        if messagebox.askyesno("Confirmación Masiva", pregunta):
            if self.db.update_accounts_category_bulk(new_cat):
                messagebox.showinfo("Éxito", f"Todas las cuentas han sido movidas a {new_cat}")
                
                # --- SINCRONIZACIÓN TOTAL ---
                self.refresh_team_ui()      # Refresca la tabla de esta pestaña (Pestaña 2)
                self.refresh_dashboard()    # Actualiza los contadores (Pestaña 1)
                
                # Intentamos llamar a reload_dist_lists si existe (Pestaña 4)
                if hasattr(self, 'reload_dist_lists'):
                    self.reload_dist_lists()
            else:
                messagebox.showerror("Error", "No se pudo realizar la actualización masiva.")
    def create_widgets(self):
        # 1. Cabecera principal
        header = tk.Frame(self.root, bg="#2d2d44", height=60)
        header.pack(fill=tk.X)
        
        lbl_header = tk.Label(header, text="⚙️ PANEL DE CONTROL V6", font=("Arial", 16, "bold"), bg="#2d2d44", fg="white")
        lbl_header.pack(pady=15)
        
        # 2. Notebook (Contenedor de pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.reload_dist_lists())
        
        # 3. Creación de los Frames (Las 5 pestañas físicas)
        self.tab_dash = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_team = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_mix = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_dist = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_tg = tk.Frame(self.notebook, bg="#1e1e2e") # <--- AQUI NACE LA 5
        self.tab_forge = tk.Frame(self.notebook, bg="#1e1e2e")

        # 4. Añadir las pestañas a la barra superior
        self.notebook.add(self.tab_dash, text="📊 1. Dashboard")
        self.notebook.add(self.tab_team, text="👥 2. Equipo y Listas")
        self.notebook.add(self.tab_mix, text="🎬 3. Creador de Tandas")
        self.notebook.add(self.tab_dist, text="🚀 4. Logística")
        self.notebook.add(self.tab_tg, text="📲 5. Bot Telegram") # <--- AQUI SE MUESTRA
        self.notebook.add(self.tab_forge, text="🔮 6. Forge de Metadata")

        # 5. Inyectar el contenido dentro de cada pestaña
        self.build_dashboard_tab()
        self.build_team_tab()
        self.build_mix_tab()
        self.build_dist_tab()
        self.build_tg_tab() # <--- AQUI SE LLAMA AL CONTENIDO
        self.build_forge_tab()
    # ==========================================
    # PESTAÑA 1: DASHBOARD
    # ==========================================
    def build_dashboard_tab(self):
        main = tk.Frame(self.tab_dash, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        cols = ("VA", "Telegram ID", "Cuenta IG", "Tipo Contenido", "Videos", "Fecha Agregado")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=20)
        
        
        for c in cols:
            self.tree.heading(c, text=c, command=lambda _c=c: self.treeview_sort_column(self.tree, _c, False))
            self.tree.column(c, width=150, anchor="center")
            
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        btn_frame = tk.Frame(main, bg="#1e1e2e")
        btn_frame.pack(fill=tk.X, pady=10)
        
        btn_cat = tk.Button(btn_frame, text="📁 Cambiar Categoría", bg="#ff6b6b", fg="white", command=self.change_account_category)
        btn_cat.pack(side=tk.LEFT, padx=5)
        
        btn_va = tk.Button(btn_frame, text="👤 Reasignar VA", bg="#00d9ff", fg="white", command=self.reassign_va)
        btn_va.pack(side=tk.LEFT, padx=5)
        
        btn_del = tk.Button(btn_frame, text="🗑️ Eliminar Cuenta", bg="#ff4757", fg="white", command=self.delete_account)
        btn_del.pack(side=tk.LEFT, padx=5)
        
        btn_ref = tk.Button(btn_frame, text="🔄 Actualizar", bg="#4ecdc4", fg="#1e1e2e", command=self.refresh_dashboard)
        btn_ref.pack(side=tk.LEFT, padx=5)

    def refresh_dashboard(self):
        for item in self.tree.get_children(): 
            self.tree.delete(item)
            
        accounts = self.db.get_all_accounts()
        vas_data = {va: self.get_va_tg_id(va) for va in self.db.get_vas()}
        
        for acc in accounts:
            va = acc.get('assigned_va', 'Sin Asignar')
            tg = vas_data.get(va, "N/A")
            fecha = acc.get('created_at', 'N/A')
            if fecha and len(fecha) >= 10:
                fecha_corta = fecha[:10]
            else:
                fecha_corta = "N/A"
                
            self.tree.insert("", "end", values=(va, tg, f"@{acc['username']}", acc['account_type'], acc.get('videos_posted', 0), fecha_corta))
            
        # Asegurarnos de actualizar las listas desplegables en otras pestañas
        if hasattr(self, 'c_bulk_cat'):
            self.refresh_team_ui()
        if hasattr(self, 'c_tandas'):
            self.reload_dist_lists()

    def get_va_tg_id(self, va_name):
        cur = self.db.conn.cursor()
        cur.execute("SELECT tg_group_id FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        if row and row['tg_group_id']:
            return row['tg_group_id']
        return "N/A"

    def get_selected_account(self):
        sel = self.tree.selection()
        if not sel: 
            messagebox.showwarning("⚠️", "Selecciona una cuenta en la tabla.")
            return None
        item_values = self.tree.item(sel[0])['values']
        return item_values[2].lstrip('@')

    def change_account_category(self):
        username = self.get_selected_account()
        if not username: 
            return
            
        categorias_existentes = self.db.get_categories()
        dialog = SelectionDialog(self.root, "Cambiar Categoría", f"Nueva categoría para @{username}", categorias_existentes)
        self.root.wait_window(dialog)
        
        if dialog.result:
            cat_upper = dialog.result.upper()
            self.db.add_category(cat_upper) 
            self.db.update_account(username, account_type=cat_upper)
            self.refresh_dashboard()
            messagebox.showinfo("✅", "Categoría actualizada.")

    def reassign_va(self):
        username = self.get_selected_account()
        if not username: 
            return
            
        vas_existentes = self.db.get_vas()
        dialog = SelectionDialog(self.root, "Reasignar VA", f"Asignar VA para @{username}", vas_existentes)
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.db.add_va(dialog.result) 
            self.db.update_account(username, assigned_va=dialog.result)
            self.refresh_dashboard()
            messagebox.showinfo("✅", "VA actualizado.")

    def delete_account(self):
        username = self.get_selected_account()
        if username:
            if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar la cuenta @{username}?"):
                self.db.delete_account(username)
                self.refresh_dashboard()

    def treeview_sort_column(self, tv, col, reverse):
        lista_elementos = [(tv.set(k, col), k) for k in tv.get_children('')]
        
        def sort_key(item):
            val = item[0]
            try:
                return (0, float(val))
            except ValueError:
                return (1, str(val).lower())
                
        lista_elementos.sort(key=sort_key, reverse=reverse)
        
        for index, (val, k) in enumerate(lista_elementos): 
            tv.move(k, '', index)
            
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    # ==========================================
    # PESTAÑA 2: EQUIPO Y CUENTAS
    # ==========================================
    def build_team_tab(self):
        main = tk.Frame(self.tab_team, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        # --- GESTOR MASIVO (BULK EDIT) ---
        f_bulk = tk.LabelFrame(main, text="⚡ Gestión Masiva de Cuentas", bg="#2d2d44", fg="#4ecdc4", font=("Arial", 11, "bold"))
        f_bulk.pack(fill=tk.X, pady=15)

        tk.Label(f_bulk, text="Mover TODAS las cuentas a:", bg="#2d2d44", fg="white").pack(side=tk.LEFT, padx=15, pady=15)
        
        # Este combo se llenará con las categorías existentes
        self.c_bulk_cat = ttk.Combobox(f_bulk, state="readonly", width=25, postcommand=self.refresh_team_ui_combo)
        self.c_bulk_cat.pack(side=tk.LEFT, padx=10)

        btn_bulk = tk.Button(f_bulk, text="APLICAR CAMBIO A TODO", bg="#ff6b6b", fg="white", 
                             font=("Arial", 10, "bold"), command=self.apply_bulk_category)
        btn_bulk.pack(side=tk.LEFT, padx=20)
        # Panel Superior: Gestión de Listas (Borrado Masivo)
        manage_frame = tk.LabelFrame(main, text="🛠️ Gestión de Listas y Limpieza Masiva", bg="#2d2d44", fg="white", font=("Arial", 10, "bold"))
        manage_frame.pack(fill=tk.X, pady=(0, 20), padx=5)
        
        btn_manage_cats = tk.Button(manage_frame, text="📋 Gestionar Categorías", bg="#4ecdc4", command=lambda: ListManager(self.root, self.db, "CATEGORIAS"))
        btn_manage_cats.pack(side=tk.LEFT, padx=20, pady=15)
        
        btn_manage_vas = tk.Button(manage_frame, text="👤 Gestionar VAs", bg="#4ecdc4", command=lambda: ListManager(self.root, self.db, "VAS"))
        btn_manage_vas.pack(side=tk.LEFT, padx=20, pady=15)
        btn_manage_accs = tk.Button(manage_frame, text="📱 Gestionar Cuentas", bg="#4ecdc4", 
                                   command=lambda: AccountManager(self.root, self.db, self.refresh_dashboard))
        btn_manage_accs.pack(side=tk.LEFT, padx=20, pady=15)
        # Panel Inferior: Contenido principal de la pestaña
        bottom_frame = tk.Frame(main, bg="#1e1e2e")
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # Izquierda: Añadir VA
        left = tk.LabelFrame(bottom_frame, text="Añadir Trabajador (VA)", bg="#2d2d44", fg="white", width=300)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        lbl_va_name = tk.Label(left, text="Nombre:", bg="#2d2d44", fg="white")
        lbl_va_name.pack(pady=(15, 5))
        
        self.e_va_name = tk.Entry(left)
        self.e_va_name.pack(pady=2)
        
        lbl_va_tg = tk.Label(left, text="Telegram ID (Opcional):", bg="#2d2d44", fg="white")
        lbl_va_tg.pack(pady=(10, 5))
        
        self.e_va_tg = tk.Entry(left)
        self.e_va_tg.pack(pady=2)
        
        btn_save_va = tk.Button(left, text="➕ Guardar VA", bg="#4ecdc4", command=self.add_va_ui)
        btn_save_va.pack(pady=20)
        
        # Derecha: Añadir Cuentas en Lote
        right = tk.LabelFrame(bottom_frame, text="Añadir Cuentas en Lote", bg="#2d2d44", fg="white")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        lbl_accounts = tk.Label(right, text="Cuentas (una por línea, sin @):", bg="#2d2d44", fg="white")
        lbl_accounts.pack(pady=5, anchor="w", padx=15)
        
        self.txt_accounts = tk.Text(right, height=8, bg="#1e1e2e", fg="white")
        self.txt_accounts.pack(fill=tk.X, padx=15)
        
        # --- Controles de asignación rápida ---
        ctrl = tk.Frame(right, bg="#2d2d44")
        ctrl.pack(fill=tk.X, pady=10, padx=15)
        
        # Fila 1: Categoría
        tk.Label(ctrl, text="Categoría:", bg="#2d2d44", fg="white").grid(row=0, column=0, sticky="w", pady=5)
        self.c_bulk_cat = ttk.Combobox(ctrl, state="readonly", width=20)
        self.c_bulk_cat.grid(row=0, column=1, padx=5, pady=5)
        
        # Fila 2: VA Asignado
        tk.Label(ctrl, text="Asignar a VA:", bg="#2d2d44", fg="white").grid(row=1, column=0, sticky="w", pady=5)
        self.c_bulk_va = ttk.Combobox(ctrl, state="readonly", width=20)
        self.c_bulk_va.grid(row=1, column=1, padx=5, pady=5)
        
        # Botonera
        btn_f = tk.Frame(right, bg="#2d2d44")
        btn_f.pack(fill=tk.X, padx=15, pady=5)
        
        btn_add_bulk = tk.Button(btn_f, text="🚀 CARGAR CUENTAS", bg="#ff6b6b", fg="white", font=("Arial", 10, "bold"), command=self.add_bulk_accounts)
        btn_add_bulk.pack(side=tk.LEFT, padx=5)
        
        btn_create_cat = tk.Button(btn_f, text="➕ Nueva Categoría", bg="#00d9ff", command=self.add_category_ui)
        btn_create_cat.pack(side=tk.LEFT, padx=5)

    def refresh_team_ui(self):
        """Llena los combos de categorías y VAs."""
        # Cargar Categorías
        cats = self.db.get_categories()
        self.c_bulk_cat.config(values=cats)
        if cats: self.c_bulk_cat.current(0)
        else: self.c_bulk_cat.set('')
        
        # Cargar VAs
        vas = self.db.get_vas()
        vas_list = ["Sin Asignar"] + vas
        self.c_bulk_va.config(values=vas_list)
        self.c_bulk_va.current(0)

    def add_category_ui(self):
        name = simpledialog.askstring("Nueva Categoría", "Nombre de la categoría (Ej: MODELOS, FITNESS):")
        if name:
            cat_upper = name.strip().upper()
            self.db.add_category(cat_upper)
            self.refresh_dashboard()
            self.refresh_team_ui() # <--- Agregar esta línea
            messagebox.showinfo("Éxito", f"Categoría '{cat_upper}' creada.")

    def add_va_ui(self):
        name = self.e_va_name.get().strip()
        tg_id = self.e_va_tg.get().strip()
        
        if name:
            self.db.add_va(name)
            if tg_id: 
                self.db.update_va_telegram_group(name, tg_id)
            
            self.e_va_name.delete(0, tk.END)
            self.e_va_tg.delete(0, tk.END)
            self.refresh_dashboard()
            self.refresh_team_ui() # <--- Esto hace que aparezca en el combo de la derecha
            messagebox.showinfo("✅", f"VA '{name}' guardado correctamente.")

    def add_bulk_accounts(self):
        texto_cuentas = self.txt_accounts.get("1.0", tk.END).strip()
        if not texto_cuentas:
            return messagebox.showwarning("⚠️", "No has escrito ninguna cuenta.")
            
        users = texto_cuentas.split("\n")
        ctype = self.c_bulk_cat.get()
        vname = self.c_bulk_va.get()
        
        # Categoría opcional: si no hay, asignamos GENERAL
        if not ctype: ctype = "GENERAL"
            
        cuentas_agregadas = 0
        for u in users:
            clean = u.strip().replace("@", "")
            if clean: 
                try:
                    # 1. Crear la cuenta con su categoría
                    self.db.add_virtual_account(clean, ctype)
                    
                    # 2. Vincular al VA si se seleccionó uno distinto a 'Sin Asignar'
                    if vname and vname != "Sin Asignar":
                        self.db.update_account(clean, assigned_va=vname)
                        
                    cuentas_agregadas += 1
                except Exception as e:
                    print(f"⚠️ Error agregando {clean}: {e}")
                    
        self.txt_accounts.delete("1.0", tk.END)
        self.refresh_dashboard()
        messagebox.showinfo("✅", f"Proceso terminado. {cuentas_agregadas} cuentas vinculadas exitosamente.")

        texto_cuentas = self.txt_accounts.get("1.0", tk.END).strip()
        if not texto_cuentas:
            return messagebox.showwarning("⚠️", "No has escrito ninguna cuenta.")
            
        users = texto_cuentas.split("\n")
        ctype = self.c_bulk_cat.get()
        
        if not ctype: 
            return messagebox.showwarning("⚠️", "Elige una categoría de la lista primero.")
            
        cuentas_agregadas = 0
        for u in users:
            clean = u.strip().replace("@", "")
            if clean: 
                try:
                    self.db.add_virtual_account(clean, ctype)
                    cuentas_agregadas += 1
                except Exception:
                    pass # Ignora silenciosamente si ya existe
                    
        self.txt_accounts.delete("1.0", tk.END)
        self.refresh_dashboard()
        messagebox.showinfo("✅", f"Se intentaron añadir las cuentas. {cuentas_agregadas} agregadas exitosamente.")

    def refresh_team_ui(self):
        """Actualiza los desplegables de Categorías y VAs en la Pestaña 2."""
        # 1. Refrescar Categorías
        cats = self.db.get_categories()
        if hasattr(self, 'c_bulk_cat'):
            self.c_bulk_cat.config(values=cats)
            if cats and not self.c_bulk_cat.get():
                self.c_bulk_cat.current(0)
        
        # 2. Refrescar VAs (Esto es lo que faltaba)
        vas = self.db.get_vas()
        vas_list = ["Sin Asignar"] + vas
        if hasattr(self, 'c_bulk_va'):
            self.c_bulk_va.config(values=vas_list)
            # Si no hay nada seleccionado, poner "Sin Asignar" por defecto
            if not self.c_bulk_va.get():
                self.c_bulk_va.current(0)

    # ==========================================
    # PESTAÑA 3: CREADOR DE TANDAS
    # ==========================================
    def build_mix_tab(self):
        main = tk.Frame(self.tab_mix, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        top = tk.Frame(main, bg="#2d2d44")
        top.pack(fill=tk.X, pady=10)
        
        lbl_tanda = tk.Label(top, text="Nombre/ID de la Tanda:", bg="#2d2d44", fg="white", font=("Arial", 11, "bold"))
        lbl_tanda.pack(side=tk.LEFT, padx=10)
        
        self.e_tanda_name = tk.Entry(top, width=30)
        self.e_tanda_name.pack(side=tk.LEFT, pady=15)
        
        split = tk.PanedWindow(main, orient=tk.HORIZONTAL, bg="#1e1e2e")
        split.pack(fill=tk.BOTH, expand=True)
        
        # Panel P1
        f1 = tk.LabelFrame(split, text="Clips de Inicio (P1)", bg="#2d2d44", fg="white", font=("Arial", 10, "bold"))
        split.add(f1, minsize=300)
        
        btn_p1 = tk.Button(f1, text="📂 Buscar Carpeta P1", command=lambda: self.pick_folder(1))
        btn_p1.pack(pady=10)
        
        self.list_p1 = tk.Listbox(f1, bg="#1e1e2e", fg="white")
        self.list_p1.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Panel P2
        f2 = tk.LabelFrame(split, text="Clips de Cierre (P2)", bg="#2d2d44", fg="white", font=("Arial", 10, "bold"))
        split.add(f2, minsize=300)
        
        btn_p2 = tk.Button(f2, text="📂 Buscar Carpeta P2", command=lambda: self.pick_folder(2))
        btn_p2.pack(pady=10)
        
        self.list_p2 = tk.Listbox(f2, bg="#1e1e2e", fg="white")
        self.list_p2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        bot = tk.Frame(main, bg="#2d2d44")
        bot.pack(fill=tk.X, pady=10)
        
        btn_cap = tk.Button(bot, text="📄 Archivo Captions (.txt)", command=self.pick_captions, bg="#ff6b6b", fg="white")
        btn_cap.pack(side=tk.LEFT, padx=15, pady=10)
        
        self.lbl_cap = tk.Label(bot, text="No seleccionado", bg="#2d2d44", fg="white")
        self.lbl_cap.pack(side=tk.LEFT)
        
        btn_render = tk.Button(bot, text="⚙️ INICIAR RENDER DE TANDA", bg="#00d9ff", font=("Arial", 11, "bold"), command=self.process_tanda)
        btn_render.pack(side=tk.RIGHT, padx=20)

    def pick_folder(self, pane_num):
        path = filedialog.askdirectory()
        if not path:
            return
            
        if pane_num == 1:
            self.p1_dir = path
            lista = self.list_p1
        else:
            self.p2_dir = path
            lista = self.list_p2
            
        lista.delete(0, tk.END)
        for f in os.listdir(path): 
            if f.lower().endswith(('.mp4', '.mov')): 
                lista.insert(tk.END, f)

    def pick_captions(self):
        path = filedialog.askopenfilename(filetypes=[("Archivos de Texto", "*.txt")])
        if path: 
            self.cap_file = path
            self.lbl_cap.config(text=os.path.basename(path))

    def process_tanda(self):
        name = self.e_tanda_name.get().strip().upper()
        if not name or not self.p1_dir or not self.p2_dir or not self.cap_file:
            return messagebox.showwarning("⚠️", "Asegúrate de llenar el nombre, P1, P2 y Captions.")
            
        # Registrar en la base de datos
        self.db.add_tanda(name, self.p1_dir, self.p2_dir, self.cap_file)
        
        def task():
            import videos
            return videos.render_tanda(name)
            
        def done(success, result):
            if success: 
                messagebox.showinfo("Éxito", result)
            else: 
                messagebox.showerror("Error", result)
                
        messagebox.showinfo("Iniciando", "El proceso de mezcla ha comenzado en segundo plano.")
        WorkerThread(self.root, done, task).start()

# ==========================================
    # PESTAÑA 4: LOGÍSTICA Y VISTA PREVIA
    # ==========================================
    def build_dist_tab(self):
        main = tk.Frame(self.tab_dist, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        f1 = tk.LabelFrame(main, text="Opciones de Distribución", bg="#2d2d44", fg="white", font=("Arial", 12, "bold"))
        f1.pack(fill=tk.X, pady=10)
        
        # --- FILA 0: Tandas y Categorías ---
        lbl_tandas = tk.Label(f1, text="Tanda a distribuir:", bg="#2d2d44", fg="white")
        lbl_tandas.grid(row=0, column=0, padx=10, pady=15, sticky="e")
        
        self.c_tandas = ttk.Combobox(f1, state="readonly", width=25, postcommand=self.reload_dist_lists)
        self.c_tandas.grid(row=0, column=1, sticky="w")

        lbl_tandas_2 = tk.Label(f1, text="2da tanda opcional:", bg="#2d2d44", fg="white")
        lbl_tandas_2.grid(row=0, column=2, padx=10, pady=15, sticky="e")

        self.c_tandas_2 = ttk.Combobox(f1, state="readonly", width=25, postcommand=self.reload_dist_lists)
        self.c_tandas_2.grid(row=0, column=3, sticky="w")
        
        lbl_dest = tk.Label(f1, text="Categoría Destino:", bg="#2d2d44", fg="white")
        lbl_dest.grid(row=1, column=0, padx=10, sticky="e")
        
        self.c_dest = ttk.Combobox(f1, state="readonly", width=25, postcommand=self.reload_dist_lists)
        self.c_dest.grid(row=1, column=1, sticky="w")
        
        # --- FILA 1: Cuota y Checkbox ---
        lbl_quota = tk.Label(f1, text="Videos diarios por cuenta:", bg="#2d2d44", fg="white")
        lbl_quota.grid(row=2, column=0, padx=10, pady=10, sticky="e")        

        self.e_quota = tk.Entry(f1, width=10)
        self.e_quota.insert(0, "4")
        self.e_quota.grid(row=2, column=1, sticky="w")
# Debajo de e_quota
        lbl_days = tk.Label(f1, text="Días (o 'MAX'):", bg="#2d2d44", fg="white")
        lbl_days.grid(row=2, column=2, padx=10, sticky="e")   

        self.e_days = tk.Entry(f1, width=10)
        self.e_days.insert(0, "MAX")
        self.e_days.grid(row=2, column=3, sticky="w")

        self.fillup_var = tk.BooleanVar()
        chk_fillup = tk.Checkbutton(f1, text="Habilitar 'Fill-up' (Rellenar con historial)", 
                                    variable=self.fillup_var, bg="#2d2d44", fg="#4ecdc4", selectcolor="#1e1e2e")
        chk_fillup.grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=8)        

        # --- Botonera de Acción ---
        btn_box = tk.Frame(main, bg="#1e1e2e")
        btn_box.pack(pady=30)
        
        btn_preview = tk.Button(btn_box, text="👁️ VISTA PREVIA", bg="#4ecdc4", fg="#1e1e2e", font=("Arial", 12, "bold"), command=self.preview_distribution)
        btn_preview.pack(side=tk.LEFT, padx=10)
        
        btn_distribute = tk.Button(btn_box, text="🚀 DISTRIBUIR REAL AHORA", bg="#ff6b6b", fg="white", font=("Arial", 12, "bold"), command=self.start_distribution)
        btn_distribute.pack(side=tk.LEFT, padx=10)
        
        self.reload_dist_lists()

    def reload_dist_lists(self, event=None):
        """Recarga las listas de tandas y categorías desde la DB."""
        try:
            tandas_raw = self.db.get_all_tandas()

            tandas = []
            for t in tandas_raw:
                if isinstance(t, dict):
                    tandas.append(t.get("tanda_name"))
                else:
                    tandas.append(t["tanda_name"])

            tandas = [t for t in tandas if t]

            if hasattr(self, "c_tandas"):
                current_1 = self.c_tandas.get()
                self.c_tandas.config(values=tandas)

                if current_1 in tandas:
                    self.c_tandas.set(current_1)
                elif tandas:
                    self.c_tandas.current(0)
                else:
                    self.c_tandas.set("")

            if hasattr(self, "c_tandas_2"):
                current_2 = self.c_tandas_2.get()
                values_2 = [""] + tandas
                self.c_tandas_2.config(values=values_2)

                if current_2 in values_2:
                    self.c_tandas_2.set(current_2)
                else:
                    self.c_tandas_2.set("")

            cats = self.db.get_categories()

            if hasattr(self, "c_dest"):
                current_dest = self.c_dest.get()
                self.c_dest.config(values=cats)

                if current_dest in cats:
                    self.c_dest.set(current_dest)
                elif cats:
                    self.c_dest.current(0)
                else:
                    self.c_dest.set("")

            if hasattr(self, 'c_forge_cat'):
                self._forge_reload_cats()

            print(f"✅ Tandas cargadas en GUI: {tandas}")
            print(f"✅ Categorías cargadas en GUI: {cats}")

        except Exception as e:
            print(f"⚠️ Error al refrescar listas: {e}")
            messagebox.showerror("Error cargando listas", str(e))

    def preview_distribution(self):
        """Genera la simulación detallada sin mover archivos físicos."""
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        tanda_2 = self.c_tandas_2.get().strip() if hasattr(self, "c_tandas_2") else ""
        # Capturamos el nuevo campo de días que añadimos anteriormente
        days_input = self.e_days.get() if hasattr(self, 'e_days') else "MAX"
        
        try: 
            quota = int(self.e_quota.get())
        except: 
            return messagebox.showwarning("⚠️", "Cuota diaria inválida.")
            
        if not tanda or not dest: 
            return messagebox.showwarning("⚠️", "Selecciona Tanda y Categoría Destino.")
            
        def task():
            import Organizador

            if tanda_2:
                return (
                    Organizador.preview_distribution_tanda(
                        tanda, dest, quota, self.fillup_var.get(), days_input
                    )
                    + "\n\n"
                    + "╔════════════════════════════════════════════════════════════════════╗\n"
                    + f"║   🎲 SEGUNDA TANDA OPCIONAL: {tanda_2:<26} ║\n"
                    + "╚════════════════════════════════════════════════════════════════════╝\n\n"
                    + Organizador.preview_distribution_tanda(
                        tanda_2, dest, quota, self.fillup_var.get(), days_input
                    )
                )

            return Organizador.preview_distribution_tanda(
                tanda, dest, quota, self.fillup_var.get(), days_input
            )
            
        def done(success, result):
            if success: 
                win = tk.Toplevel(self.root)
                win.title(f"📊 Plan de Distribución: {tanda}")
                win.geometry("900x700")
                win.configure(bg="#1e1e2e")
                
                # Usamos una fuente monoespaciada para que las tablas ASCII se vean perfectas
                txt = tk.Text(win, bg="#2d2d44", fg="#4ecdc4", font=("Consolas", 10), padx=20, pady=20)
                txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                txt.insert(tk.END, result)
                txt.config(state=tk.DISABLED)
            else: 
                messagebox.showerror("Error en Simulación", result)
        
        messagebox.showinfo("Calculando", "Analizando inventario y asignación de VAs...")
        WorkerThread(self.root, done, task).start()

    def start_distribution(self):
        """Ejecuta la distribución real de videos."""
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        days_input = self.e_days.get() # <--- Capturamos los días ("MAX" o número)
        tanda_2 = self.c_tandas_2.get().strip() if hasattr(self, "c_tandas_2") else ""
        if tanda_2 == tanda:
            tanda_2 = ""
        
        try:
            quota = int(self.e_quota.get())
        except:
            return messagebox.showwarning("⚠️", "Meta diaria inválida.")
            
        if not tanda or not dest: 
            return messagebox.showwarning("⚠️", "Faltan datos.")
        
        label_tandas = tanda if not tanda_2 else f"{tanda} + {tanda_2}"

        if not messagebox.askyesno("Confirmación", f"¿Distribuir '{label_tandas}' a la categoría '{dest}'?"):
            return
            
        def task():
            import Organizador
            return Organizador.distribute_tanda(
                tanda,
                dest,
                quota,
                self.fillup_var.get(),
                days_input,
                tanda_name_2=tanda_2 if tanda_2 else None
         )
            
        def done(success, result):
            if success: messagebox.showinfo("Éxito", result)
            else: messagebox.showerror("Error", result)
            self.refresh_dashboard()
            
        WorkerThread(self.root, done, task).start()

    def refresh_team_ui_combo(self):
        cats = self.db.get_categories()
        if hasattr(self, 'c_bulk_cat'):
            self.c_bulk_cat.config(values=cats)

    # ==========================================
    # PESTAÑA 5: COMANDO BOT TELEGRAM
    # ==========================================
    def build_tg_tab(self):
        self.tg_controller = None
        
        main = tk.Frame(self.tab_tg, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 1. Configuración de Fecha
        f_config = tk.LabelFrame(main, text="1. Fecha de Inicio", bg="#2d2d44", fg="#00d9ff", font=("Arial", 11, "bold"))
        f_config.pack(fill=tk.X, pady=5, padx=10)
        
        from datetime import datetime, timedelta
        # Por defecto sugiere empezar mañana
        mañana_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        tk.Label(f_config, text="Día 1 de Publicación (YYYY-MM-DD):", bg="#2d2d44", fg="white").pack(side=tk.LEFT, padx=10, pady=10)
        self.e_tg_date = tk.Entry(f_config, width=15)
        self.e_tg_date.insert(0, mañana_str)
        self.e_tg_date.pack(side=tk.LEFT, padx=5)
        
        # 2. Selección de Objetivos
        f_target = tk.LabelFrame(main, text="2. Selección de Cuentas (CALENDARIO_POSTEO)", bg="#2d2d44", fg="#00d9ff", font=("Arial", 11, "bold"))
        f_target.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)
        
        scroll = tk.Scrollbar(f_target)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.lst_tg_accs = tk.Listbox(f_target, selectmode=tk.MULTIPLE, bg="#1e1e2e", fg="white", yscrollcommand=scroll.set, font=("Consolas", 10))
        self.lst_tg_accs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scroll.config(command=self.lst_tg_accs.yview)
        
        btn_refresh = tk.Button(f_target, text="🔄 Cargar Cuentas Listas", bg="#4ecdc4", fg="black", command=self.load_organized_accounts)
        btn_refresh.pack(pady=5)
        
        # 3. Controles de Ejecución (Hilos)
        f_ctrl = tk.Frame(main, bg="#1e1e2e")
        f_ctrl.pack(pady=15)
        
        self.btn_tg_start = tk.Button(f_ctrl, text="▶️ INICIAR ENVÍOS", bg="#20c997", fg="white", font=("Arial", 12, "bold"), width=18, command=self.start_tg_bot)
        self.btn_tg_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_tg_pause = tk.Button(f_ctrl, text="⏸️ PAUSAR", bg="#f39c12", fg="white", font=("Arial", 12, "bold"), width=12, command=self.pause_tg_bot, state=tk.DISABLED)
        self.btn_tg_pause.pack(side=tk.LEFT, padx=10)
        
        self.btn_tg_stop = tk.Button(f_ctrl, text="⏹️ TERMINAR", bg="#ff4757", fg="white", font=("Arial", 12, "bold"), width=12, command=self.stop_tg_bot, state=tk.DISABLED)
        self.btn_tg_stop.pack(side=tk.LEFT, padx=10)

    def load_organized_accounts(self):
        """Escanea CALENDARIO_POSTEO para poblar la lista."""
        self.lst_tg_accs.delete(0, tk.END)
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CALENDARIO_POSTEO")
        accs = set()
        if os.path.exists(base):
            for d in os.listdir(base):
                path = os.path.join(base, d)
                if os.path.isdir(path):
                    for a in os.listdir(path):
                        if os.path.isdir(os.path.join(path, a)): accs.add(a)
        if accs:
            for a in sorted(list(accs)): self.lst_tg_accs.insert(tk.END, a)
        else:
            messagebox.showinfo("Vacío", "Ejecuta la Logística (Pestaña 4) primero para crear carpetas.")

    def start_tg_bot(self):
        date_str = self.e_tg_date.get().strip()
        try:
            from datetime import datetime
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError: 
            return messagebox.showwarning("⚠️", "Usa YYYY-MM-DD.")
        
        selected = [self.lst_tg_accs.get(i) for i in self.lst_tg_accs.curselection()]
        
        # Si no hay selección, preguntar si enviar todas
        if not selected:
            if not messagebox.askyesno("Masivo", "No seleccionaste cuentas. ¿Enviar TODAS las disponibles?"):
                return
            selected = None  # Enviar todas
        
        self.btn_tg_start.config(state=tk.DISABLED)
        self.btn_tg_pause.config(state=tk.NORMAL, text="⏸️ PAUSAR")
        self.btn_tg_stop.config(state=tk.NORMAL)
        
        import organizadortg
        self.tg_controller = organizadortg.TelegramBotController(date_str, selected)
        
        def task():
            return organizadortg.execute_telegram_plan(start_date, selected, self.tg_controller)
            
        def done(success, result):
            self.btn_tg_start.config(state=tk.NORMAL)
            self.btn_tg_pause.config(state=tk.DISABLED)
            self.btn_tg_stop.config(state=tk.DISABLED)
            self.tg_controller = None
            messagebox.showinfo("Bot", result) if success else messagebox.showerror("Error", result)
            
        WorkerThread(self.root, done, task).start()

    def pause_tg_bot(self):
        if not self.tg_controller: return
        if self.tg_controller.paused.is_set():
            self.tg_controller.pause()
            self.btn_tg_pause.config(text="▶️ REANUDAR", bg="#3498db")
        else:
            self.tg_controller.resume()
            self.btn_tg_pause.config(text="⏸️ PAUSAR", bg="#f39c12")
            
    def stop_tg_bot(self):
        if self.tg_controller:
            self.tg_controller.stop()
            self.tg_controller.resume()

    # ==========================================
    # PESTAÑA 6: FORGE DE METADATA
    # ==========================================
    def build_forge_tab(self):
        self.forge_video_paths = []
        self.forge_meta_assignments = []

        main = tk.Frame(self.tab_forge, bg="#1e1e2e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # --- TOP: dos columnas (video list | config) ---
        top = tk.Frame(main, bg="#1e1e2e")
        top.pack(fill=tk.X, pady=(0, 8))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        # PASO 1 — Lista de videos
        f_videos = tk.LabelFrame(top, text="1. Videos a Procesar", bg="#2d2d44", fg="#00d9ff", font=("Arial", 11, "bold"))
        f_videos.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        scroll_v = tk.Scrollbar(f_videos)
        scroll_v.pack(side=tk.RIGHT, fill=tk.Y)
        self.forge_lst = tk.Listbox(f_videos, selectmode=tk.EXTENDED, bg="#1e1e2e", fg="white",
                                    yscrollcommand=scroll_v.set, font=("Consolas", 9), height=9)
        self.forge_lst.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        scroll_v.config(command=self.forge_lst.yview)

        btn_row = tk.Frame(f_videos, bg="#2d2d44")
        btn_row.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(btn_row, text="+ Agregar Videos", bg="#4ecdc4", fg="#1e1e2e",
                  font=("Arial", 9, "bold"), command=self.forge_add_videos).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_row, text="− Quitar", bg="#ff6b6b", fg="white",
                  font=("Arial", 9, "bold"), command=self.forge_remove_video).pack(side=tk.LEFT)

        self.forge_lbl_count = tk.Label(f_videos, text="Total: 0 videos", bg="#2d2d44", fg="#aaaaaa", font=("Arial", 9))
        self.forge_lbl_count.pack(pady=(0, 8))

        # PASO 2 — Configuración
        f_config = tk.LabelFrame(top, text="2. Configuración", bg="#2d2d44", fg="#00d9ff", font=("Arial", 11, "bold"))
        f_config.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        def _lbl(text, row):
            tk.Label(f_config, text=text, bg="#2d2d44", fg="white",
                     anchor="e", font=("Arial", 10)).grid(row=row, column=0, padx=10, pady=7, sticky="e")

        _lbl("Nombre de tanda:", 0)
        self.e_forge_tanda = tk.Entry(f_config, width=22, bg="#1e1e2e", fg="white", insertbackground="white")
        self.e_forge_tanda.grid(row=0, column=1, padx=10, pady=7, sticky="w")

        _lbl("Categoría destino:", 1)
        self.c_forge_cat = ttk.Combobox(f_config, state="readonly", width=20)
        self.c_forge_cat.grid(row=1, column=1, padx=10, pady=7, sticky="w")
        self.c_forge_cat.config(postcommand=self._forge_reload_cats)
        self._forge_reload_cats()

        _lbl("Videos/cuenta/día:", 2)
        self.e_forge_quota = tk.Entry(f_config, width=8, bg="#1e1e2e", fg="white", insertbackground="white")
        self.e_forge_quota.insert(0, "4")
        self.e_forge_quota.grid(row=2, column=1, padx=10, pady=7, sticky="w")

        _lbl("Días a distribuir:", 3)
        self.e_forge_days = tk.Entry(f_config, width=8, bg="#1e1e2e", fg="white", insertbackground="white")
        self.e_forge_days.insert(0, "MAX")
        self.e_forge_days.grid(row=3, column=1, padx=10, pady=7, sticky="w")

        self.forge_dist_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f_config, text="Distribuir automáticamente al procesar",
                       variable=self.forge_dist_var, bg="#2d2d44", fg="#4ecdc4",
                       selectcolor="#1e1e2e").grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 10))

        # --- TABLA PREVIEW ---
        f_preview = tk.LabelFrame(main, text="Vista Previa de Metadata", bg="#2d2d44", fg="#00d9ff", font=("Arial", 11, "bold"))
        f_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("Video", "Modelo iPhone", "Ciudad", "Carrier", "iOS")
        self.forge_tree = ttk.Treeview(f_preview, columns=cols, show="headings", height=7)
        col_widths = {"Video": 160, "Modelo iPhone": 170, "Ciudad": 130, "Carrier": 150, "iOS": 70}
        for col in cols:
            self.forge_tree.heading(col, text=col)
            self.forge_tree.column(col, width=col_widths[col], anchor="center")
        scr_tree = ttk.Scrollbar(f_preview, orient="vertical", command=self.forge_tree.yview)
        self.forge_tree.configure(yscrollcommand=scr_tree.set)
        self.forge_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        scr_tree.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)

        # --- BOTONERA ---
        btn_bar = tk.Frame(main, bg="#1e1e2e")
        btn_bar.pack(pady=6)

        tk.Button(btn_bar, text="👁️ Preview Metadata", bg="#4ecdc4", fg="#1e1e2e",
                  font=("Arial", 11, "bold"), command=self.forge_preview_metadata).pack(side=tk.LEFT, padx=8)

        self.btn_forge_reshuffle = tk.Button(btn_bar, text="🔀 Regenerar Shuffle", bg="#f39c12", fg="white",
                                             font=("Arial", 11, "bold"), command=self.forge_reshuffle,
                                             state=tk.DISABLED)
        self.btn_forge_reshuffle.pack(side=tk.LEFT, padx=8)

        self.btn_forge_process = tk.Button(btn_bar, text="⚡ Procesar Ahora", bg="#ff6b6b", fg="white",
                                           font=("Arial", 11, "bold"), command=self.forge_process,
                                           state=tk.DISABLED)
        self.btn_forge_process.pack(side=tk.LEFT, padx=8)

        # --- PROGRESO ---
        prog_frame = tk.Frame(main, bg="#1e1e2e")
        prog_frame.pack(fill=tk.X, pady=(4, 0))

        self.forge_progress = ttk.Progressbar(prog_frame, mode="determinate", length=420)
        self.forge_progress.pack(side=tk.LEFT, padx=(0, 10))

        self.forge_progress_lbl = tk.Label(prog_frame, text="Listo.", bg="#1e1e2e", fg="#aaaaaa", font=("Arial", 9))
        self.forge_progress_lbl.pack(side=tk.LEFT)

    def _forge_reload_cats(self):
        cats = self.db.get_categories()
        self.c_forge_cat.config(values=cats)
        if cats and not self.c_forge_cat.get():
            self.c_forge_cat.current(0)

    def forge_add_videos(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar Videos",
            filetypes=[("Video", "*.mp4 *.mov"), ("Todos los archivos", "*.*")]
        )
        for p in paths:
            if p not in self.forge_video_paths:
                self.forge_video_paths.append(p)
                self.forge_lst.insert(tk.END, os.path.basename(p))
        self.forge_lbl_count.config(text=f"Total: {len(self.forge_video_paths)} videos")

    def forge_remove_video(self):
        for idx in reversed(self.forge_lst.curselection()):
            self.forge_lst.delete(idx)
            self.forge_video_paths.pop(idx)
        self.forge_lbl_count.config(text=f"Total: {len(self.forge_video_paths)} videos")

    def forge_preview_metadata(self):
        n = len(self.forge_video_paths)
        if n == 0:
            return messagebox.showwarning("⚠️", "Agrega al menos un video primero.")
        try:
            import metadata_pool
            self.forge_meta_assignments = metadata_pool.generate_unique_metadata(self.db, n)
        except ValueError as e:
            return messagebox.showerror("Sin combinaciones disponibles", str(e))

        for item in self.forge_tree.get_children():
            self.forge_tree.delete(item)
        for i, path in enumerate(self.forge_video_paths):
            m = self.forge_meta_assignments[i]
            self.forge_tree.insert("", tk.END, values=(
                os.path.basename(path), m["iphone_model"], m["city"], m["carrier"], m["ios_version"]
            ))
        self.btn_forge_process.config(state=tk.NORMAL)
        self.btn_forge_reshuffle.config(state=tk.NORMAL)
        self.forge_progress_lbl.config(text=f"✅ {n} asignaciones generadas. Revisá la tabla y presioná Procesar.")

    def forge_reshuffle(self):
        self.forge_preview_metadata()

    def forge_process(self):
        if not self.forge_video_paths:
            return messagebox.showwarning("⚠️", "No hay videos en la lista.")
        if not self.forge_meta_assignments:
            return messagebox.showwarning("⚠️", "Generá el preview primero.")

        tanda_name = self.e_forge_tanda.get().strip()
        category = self.c_forge_cat.get()
        auto_dist = self.forge_dist_var.get()

        if not tanda_name:
            return messagebox.showwarning("⚠️", "Ingresá un nombre para la tanda Forge.")
        if not category:
            return messagebox.showwarning("⚠️", "Seleccioná una categoría destino.")

        try:
            quota = int(self.e_forge_quota.get())
        except ValueError:
            return messagebox.showwarning("⚠️", "Cuota diaria inválida.")

        days_input = self.e_forge_days.get().strip() or "MAX"

        if not messagebox.askyesno("Confirmar Forge", (
            f"¿Procesar {len(self.forge_video_paths)} videos con metadata iPhone única?\n\n"
            f"Tanda: {tanda_name}\n"
            f"Categoría: {category}\n"
            f"Distribuir automáticamente: {'Sí' if auto_dist else 'No'}"
        )):
            return

        videos = self.forge_video_paths[:]
        meta_list = self.forge_meta_assignments[:]
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        db_ref = self.db

        self.btn_forge_process.config(state=tk.DISABLED)
        self.btn_forge_reshuffle.config(state=tk.DISABLED)
        self.forge_progress.config(mode="indeterminate")
        self.forge_progress.start(10)
        self.forge_progress_lbl.config(text="Procesando con FFmpeg...")

        def task():
            import metadata_pool
            os.makedirs(output_dir, exist_ok=True)
            fingerprints = []

            for i, (vid_path, meta) in enumerate(zip(videos, meta_list)):
                filename = os.path.basename(vid_path)
                base, ext = os.path.splitext(filename)
                p1 = base.replace("__", "_")  # evita romper el parser de P1/P2
                out_name = f"{tanda_name}__{p1}__v{i:04d}{ext}"
                out_path = os.path.join(output_dir, out_name)
                metadata_pool.apply_metadata_to_video(vid_path, out_path, meta)
                fingerprints.append({
                    "video_hash": metadata_pool.get_video_hash(vid_path),
                    **meta,
                })

            db_ref.save_metadata_fingerprints(fingerprints)
            db_ref.add_tanda(tanda_name, tanda_name, tanda_name, "")

            msg = (
                f"✅ {len(videos)} videos procesados con metadata iPhone.\n"
                f"📁 Guardados en: videos_finales/{tanda_name}/\n"
                f"🔮 Tanda '{tanda_name}' registrada en la DB."
            )

            if auto_dist:
                import Organizador
                dist_result = Organizador.distribute_tanda(
                    tanda_name, category, quota, False, days_input
                )
                msg += f"\n\n{dist_result}"

            return msg

        def done(success, result):
            self.btn_forge_process.config(state=tk.NORMAL)
            self.btn_forge_reshuffle.config(state=tk.NORMAL)
            self.forge_progress.stop()
            self.forge_progress.config(mode="determinate", value=100 if success else 0)
            if success:
                self.forge_progress_lbl.config(text="✅ Completado")
                messagebox.showinfo("✅ Forge completado", result)
                self.reload_dist_lists()
            else:
                self.forge_progress_lbl.config(text="❌ Error")
                messagebox.showerror("Error en Forge", result)

        WorkerThread(self.root, done, task).start()


# ==========================================
# PUNTO DE ENTRADA
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    
    # Inyectamos el postcommand al combo de la pestaña 2 que ya estaba creado arriba
    if hasattr(app, 'c_bulk_cat'):
        app.c_bulk_cat.config(postcommand=app.refresh_team_ui_combo)
        
    root.mainloop()