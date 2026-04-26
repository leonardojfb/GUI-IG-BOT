"""
🎨 GUI UNIFICADA - V6 (Código Expandido y Estructurado)
Gestión Total, Limpieza Masiva y Anti-Choque Global.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import threading
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
        header = tk.Frame(self.root, bg="#2d2d44", height=60)
        header.pack(fill=tk.X)
        
        lbl_header = tk.Label(header, text="⚙️ PANEL DE CONTROL V6", font=("Arial", 16, "bold"), bg="#2d2d44", fg="white")
        lbl_header.pack(pady=15)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.reload_dist_lists())
        
        self.tab_dash = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_team = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_mix = tk.Frame(self.notebook, bg="#1e1e2e")
        self.tab_dist = tk.Frame(self.notebook, bg="#1e1e2e")
        
        self.notebook.add(self.tab_dash, text="📊 1. Dashboard")
        self.notebook.add(self.tab_team, text="👥 2. Equipo y Listas")
        self.notebook.add(self.tab_mix, text="🎬 3. Creador de Tandas")
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
        
        ctrl = tk.Frame(right, bg="#2d2d44")
        ctrl.pack(fill=tk.X, pady=10, padx=15)
        
        lbl_bulk_cat = tk.Label(ctrl, text="Seleccionar Categoría:", bg="#2d2d44", fg="white")
        lbl_bulk_cat.pack(side=tk.LEFT)
        
        self.c_bulk_cat = ttk.Combobox(ctrl, state="readonly", postcommand=self.refresh_team_ui)
        self.c_bulk_cat.pack(side=tk.LEFT, padx=5)
        
        btn_add_bulk = tk.Button(ctrl, text="🚀 Cargar Cuentas", bg="#ff6b6b", fg="white", command=self.add_bulk_accounts)
        btn_add_bulk.pack(side=tk.LEFT, padx=10)
        
        btn_create_cat = tk.Button(ctrl, text="➕ Crear Nueva Categoría", bg="#00d9ff", command=self.add_category_ui)
        btn_create_cat.pack(side=tk.LEFT)
        
        self.refresh_team_ui()

    def add_category_ui(self):
        name = simpledialog.askstring("Nueva Categoría", "Nombre de la categoría (Ej: MODELOS, FITNESS):")
        if name:
            cat_upper = name.strip().upper()
            self.db.add_category(cat_upper)
            messagebox.showinfo("Éxito", f"Categoría '{cat_upper}' creada.")
            self.refresh_dashboard()

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

    def add_bulk_accounts(self):
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
        cats = self.db.get_categories()
        self.c_bulk_cat.config(values=cats)
        if cats: 
            self.c_bulk_cat.current(0)
        else:
            self.c_bulk_cat.set('')

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
        
        lbl_dest = tk.Label(f1, text="Categoría Destino:", bg="#2d2d44", fg="white")
        lbl_dest.grid(row=0, column=2, padx=10, sticky="e")
        
        self.c_dest = ttk.Combobox(f1, state="readonly", width=25, postcommand=self.reload_dist_lists)
        self.c_dest.grid(row=0, column=3, sticky="w")
        
        # --- FILA 1: Cuota y Checkbox ---
        lbl_quota = tk.Label(f1, text="Videos diarios por cuenta:", bg="#2d2d44", fg="white")
        lbl_quota.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        
        self.e_quota = tk.Entry(f1, width=10)
        self.e_quota.insert(0, "4")
        self.e_quota.grid(row=1, column=1, sticky="w")
        lbl_days = tk.Label(f1, text="Días a organizar (o 'MAX'):", bg="#2d2d44", fg="white")
        lbl_days.grid(row=1, column=2, padx=10, sticky="e")
        
        self.e_days = tk.Entry(f1, width=10)
        self.e_days.insert(0, "MAX")
        self.e_days.grid(row=1, column=3, sticky="w")
        self.fillup_var = tk.BooleanVar()
        chk_fillup = tk.Checkbutton(f1, text="Habilitar 'Fill-up' (Rellenar con historial)", 
                                    variable=self.fillup_var, bg="#2d2d44", fg="#4ecdc4", selectcolor="#1e1e2e")
        chk_fillup.grid(row=1, column=2, columnspan=2, sticky="w")
        
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
            tandas = [t['tanda_name'] for t in tandas_raw]
            if hasattr(self, 'c_tandas'):
                self.c_tandas.config(values=tandas)
                if tandas and not self.c_tandas.get():
                    self.c_tandas.current(0)
            
            cats = self.db.get_categories()
            if hasattr(self, 'c_dest'):
                self.c_dest.config(values=cats)
                if cats and not self.c_dest.get():
                    self.c_dest.current(0)
        except Exception as e:
            print(f"⚠️ Error al refrescar listas: {e}")

    def preview_distribution(self):
        """Genera la simulación sin mover archivos."""
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        days_input = self.e_days.get()
        try: quota = int(self.e_quota.get())
        except: return messagebox.showwarning("⚠️", "Cuota diaria inválida.")
            
        if not tanda or not dest: return messagebox.showwarning("⚠️", "Faltan datos.")
            
        def task():
            import Organizador
            # Pasamos todos los parámetros a la nueva lógica
            return Organizador.preview_distribution_tanda(tanda, dest, quota, self.fillup_var.get(), days_input)
            
        def task():
            import Organizador
            return Organizador.preview_distribution_tanda(tanda, dest, quota, self.fillup_var.get())
            
        def done(success, result):
            if success: 
                win = tk.Toplevel(self.root)
                win.title(f"Vista Previa: {tanda}")
                win.geometry("800x600")
                win.configure(bg="#1e1e2e")
                txt = tk.Text(win, bg="#2d2d44", fg="#4ecdc4", font=("Consolas", 11), padx=15, pady=15)
                txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                txt.insert(tk.END, result)
                txt.config(state=tk.DISABLED)
            else: 
                messagebox.showerror("Error", result)
        
        messagebox.showinfo("Calculando", "Generando árbol de distribución...")
        WorkerThread(self.root, done, task).start()

    def start_distribution(self):
        """Ejecuta la distribución real de videos."""
        tanda = self.c_tandas.get()
        dest = self.c_dest.get()
        try:
            quota = int(self.e_quota.get())
        except:
            return messagebox.showwarning("⚠️", "Meta diaria inválida.")
            
        if not tanda or not dest: 
            return messagebox.showwarning("⚠️", "Faltan datos.")
        
        if not messagebox.askyesno("Confirmación", "¿Mover archivos y registrar en DB?"):
            return
            
        def task():
            import Organizador
            return Organizador.distribute_tanda(tanda, dest, quota, self.fillup_var.get())
            
        def done(success, result):
            if success: messagebox.showinfo("Éxito", result)
            else: messagebox.showerror("Error", result)
            self.refresh_dashboard()
            
        WorkerThread(self.root, done, task).start()

    def refresh_team_ui_combo(self):
        cats = self.db.get_categories()
        if hasattr(self, 'c_bulk_cat'):
            self.c_bulk_cat.config(values=cats)

if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    
    # Inyectamos el postcommand al combo de la pestaña 2 que ya estaba creado arriba
    if hasattr(app, 'c_bulk_cat'):
        app.c_bulk_cat.config(postcommand=app.refresh_team_ui_combo)
        
    root.mainloop()