"""
🎨 INTERFAZ GRÁFICA - ORGANIZADOR DE VIDEOS INSTAGRAM
Permite controlar cuentas, mezclas de videos y distribución
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import random
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_ROOT = os.path.join(BASE_DIR, "videos_finales")
OUTPUT_ROOT = os.path.join(BASE_DIR, "CALENDARIO_POSTEO")
ACCOUNTS_PROMO_FILE = os.path.join(BASE_DIR, "accounts_promo.txt")
ACCOUNTS_SUICIDE_FILE = os.path.join(BASE_DIR, "accounts_suicide.txt")
STATE_FILE = os.path.join(BASE_DIR, "telegram_state_v11.json")

# ==================== CLASE PRINCIPAL ====================
class InstagramOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Organizador de Videos - Instagram")
        self.root.geometry("1100x750")
        self.root.configure(bg="#1a1a2e")
        
        # Variables de control
        self.accounts_promo = []
        self.accounts_suicide = []
        self.selected_promo = []
        self.selected_suicide = []
        self.mix_config = {
            "suicide_count": 22,
            "promo_count": 24,
            "use_all_suicide": True,
            "use_all_promo": True
        }
        
        # Cargar datos iniciales
        self.load_accounts()
        
        # Crear interfaz
        self.create_widgets()
        self.refresh_inventory_display()
        
    def load_accounts(self):
        """Cargar cuentas desde archivos"""
        try:
            with open(ACCOUNTS_PROMO_FILE, 'r', encoding='utf-8') as f:
                self.accounts_promo = [line.strip() for line in f if line.strip()]
            with open(ACCOUNTS_SUICIDE_FILE, 'r', encoding='utf-8') as f:
                self.accounts_suicide = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error cargando cuentas: {e}")
            
    def save_accounts(self):
        """Guardar cuentas a archivos"""
        try:
            with open(ACCOUNTS_PROMO_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.accounts_promo))
            with open(ACCOUNTS_SUICIDE_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.accounts_suicide))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar las cuentas: {e}")
            
    def get_inventory(self):
        """Obtener inventario de videos"""
        inventory = {"SUICIDE": {}, "PROMO": {}}
        
        for cat in ["suicide", "promo"]:
            cat_path = os.path.join(SOURCE_ROOT, cat)
            cat_key = cat.upper()
            
            if os.path.exists(cat_path):
                files = [f for f in os.listdir(cat_path) if f.lower().endswith(('.mp4', '.mov'))]
                inventory[cat_key] = {"total": len(files), "files": files}
            else:
                inventory[cat_key] = {"total": 0, "files": []}
                
        return inventory
    
    def create_widgets(self):
        """Crear todos los widgets de la interfaz"""
        
        # ==================== TÍTULO ====================
        title_frame = tk.Frame(self.root, bg="#1a1a2e", height=60)
        title_frame.pack(fill=tk.X, pady=10)
        
        title_label = tk.Label(
            title_frame, 
            text="🎬 ORGANIZADOR DE VIDEOS INSTAGRAM",
            font=("Arial", 20, "bold"),
            bg="#1a1a2e",
            fg="#00d9ff"
        )
        title_label.pack()
        
        # ==================== NOTEBOOK (PESTAÑAS) ====================
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Pestañas
        self.tab_control = tk.Frame(self.notebook, bg="#16213e")
        self.tab_distribute = tk.Frame(self.notebook, bg="#16213e")
        self.tab_accounts = tk.Frame(self.notebook, bg="#16213e")
        self.tab_mix = tk.Frame(self.notebook, bg="#16213e")
        
        self.notebook.add(self.tab_control, text="📊 Control General")
        self.notebook.add(self.tab_distribute, text="📅 Distribución por Días")
        self.notebook.add(self.tab_accounts, text="👥 Cuentas")
        self.notebook.add(self.tab_mix, text="🎞️ Mezclas de Videos")
        
        # Crear contenido de cada pestaña
        self.create_control_tab()
        self.create_distribute_tab()
        self.create_accounts_tab()
        self.create_mix_tab()
        
    def create_control_tab(self):
        """Pestaña de Control General"""
        main_frame = tk.Frame(self.tab_control, bg="#16213e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- ESTADO DEL INVENTARIO ---
        inv_frame = tk.LabelFrame(main_frame, text="📦 Inventario de Videos", 
                                   bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        inv_frame.pack(fill=tk.X, pady=5)
        
        self.inventory_text = tk.Text(inv_frame, height=8, width=80, bg="#0f3460", fg="white")
        self.inventory_text.pack(padx=5, pady=5)
        
        # Botones de actualización
        btn_frame = tk.Frame(inv_frame, bg="#16213e")
        btn_frame.pack(pady=5)
        
        tk.Button(btn_frame, text="🔄 Actualizar Inventario", 
                  command=self.refresh_inventory_display,
                  bg="#e94560", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # --- ACCIONES RÁPIDAS ---
        action_frame = tk.LabelFrame(main_frame, text="⚡ Acciones Rápidas", 
                                      bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        action_frame.pack(fill=tk.X, pady=10)
        
        btn_actions = tk.Frame(action_frame, bg="#16213e")
        btn_actions.pack(pady=10)
        
        tk.Button(btn_frame, text="🎞️ Crear Mezcla de Videos", 
                  command=lambda: self.notebook.select(3),
                  bg="#00d9ff", fg="black", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📅 Distribuir por Días", 
                  command=lambda: self.notebook.select(1),
                  bg="#00d9ff", fg="black", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # --- ESTADÍSTICAS ---
        stats_frame = tk.LabelFrame(main_frame, text="📈 Estadísticas", 
                                     bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_text = tk.Text(stats_frame, height=6, width=80, bg="#0f3460", fg="white")
        self.stats_text.pack(padx=5, pady=5)
        
        self.update_stats()
        
    def create_distribute_tab(self):
        """Pestaña de Distribución por Días"""
        main_frame = tk.Frame(self.tab_distribute, bg="#16213e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configuración
        config_frame = tk.LabelFrame(main_frame, text="⚙️ Configuración de Distribución", 
                                       bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        config_frame.pack(fill=tk.X, pady=5)
        
        config_inner = tk.Frame(config_frame, bg="#16213e")
        config_inner.pack(pady=10)
        
        tk.Label(config_inner, text="Videos Suicide por día:", bg="#16213e", fg="white").grid(row=0, column=0, padx=5)
        self.entry_suicide_count = tk.Entry(config_inner, width=10)
        self.entry_suicide_count.insert(0, "22")
        self.entry_suicide_count.grid(row=0, column=1, padx=5)
        
        tk.Label(config_inner, text="Videos Promo por día:", bg="#16213e", fg="white").grid(row=0, column=2, padx=5)
        self.entry_promo_count = tk.Entry(config_inner, width=10)
        self.entry_promo_count.insert(0, "24")
        self.entry_promo_count.grid(row=0, column=3, padx=5)
        
        tk.Label(config_inner, text="Días a crear:", bg="#16213e", fg="white").grid(row=0, column=4, padx=5)
        self.entry_days = tk.Entry(config_inner, width=10)
        self.entry_days.insert(0, "10")
        self.entry_days.grid(row=0, column=5, padx=5)
        
        # Botón ejecutar
        tk.Button(config_inner, text="🚀 EJECUTAR DISTRIBUCIÓN", 
                  command=self.run_distribution,
                  bg="#e94560", fg="white", font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=6, pady=15)
        
        # Vista previa
        preview_frame = tk.LabelFrame(main_frame, text="👀 Vista Previa", 
                                        bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.preview_text = tk.Text(preview_frame, height=20, bg="#0f3460", fg="white")
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def create_accounts_tab(self):
        """Pestaña de Cuentas"""
        main_frame = tk.Frame(self.tab_accounts, bg="#16213e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Cuentas Promo
        promo_frame = tk.LabelFrame(main_frame, text="👥 Cuentas PROMO", 
                                     bg="#16213e", fg="#00d9ff", font=("Arial", 11, "bold"))
        promo_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.list_promo = tk.Listbox(promo_frame, selectmode=tk.EXTENDED, bg="#0f3460", fg="white")
        self.list_promo.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        promo_btns = tk.Frame(promo_frame, bg="#16213e")
        promo_btns.pack(pady=5)
        
        tk.Button(promo_btns, text="➕ Agregar", command=self.add_promo_account,
                  bg="#00d9ff", fg="black").pack(side=tk.LEFT, padx=2)
        tk.Button(promo_btns, text="➖ Eliminar", command=self.remove_promo_account,
                  bg="#e94560", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(promo_btns, text="💾 Guardar", command=self.save_accounts,
                  bg="#4ecca3", fg="black").pack(side=tk.LEFT, padx=2)
        
        # Cuentas Suicide
        suicide_frame = tk.LabelFrame(main_frame, text="👥 Cuentas SUICIDE", 
                                        bg="#16213e", fg="#e94560", font=("Arial", 11, "bold"))
        suicide_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.list_suicide = tk.Listbox(suicide_frame, selectmode=tk.EXTENDED, bg="#0f3460", fg="white")
        self.list_suicide.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        suicide_btns = tk.Frame(suicide_frame, bg="#16213e")
        suicide_btns.pack(pady=5)
        
        tk.Button(suicide_btns, text="➕ Agregar", command=self.add_suicide_account,
                  bg="#00d9ff", fg="black").pack(side=tk.LEFT, padx=2)
        tk.Button(suicide_btns, text="➖ Eliminar", command=self.remove_suicide_account,
                  bg="#e94560", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(suicide_btns, text="💾 Guardar", command=self.save_accounts,
                  bg="#4ecca3", fg="black").pack(side=tk.LEFT, padx=2)
        
        # Llenar listas
        self.refresh_account_lists()
        
    def create_mix_tab(self):
        """Pestaña de Mezclas de Videos"""
        main_frame = tk.Frame(self.tab_mix, bg="#16213e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configuración de mezcla
        mix_config_frame = tk.LabelFrame(main_frame, text="🎞️ Configurar Mezcla", 
                                          bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        mix_config_frame.pack(fill=tk.X, pady=5)
        
        config_grid = tk.Frame(mix_config_frame, bg="#16213e")
        config_grid.pack(pady=10)
        
        # Suicide
        tk.Label(config_grid, text="Videos SUICIDE:", bg="#16213e", fg="#e94560", 
                 font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5, pady=5)
        
        self.var_use_all_suicide = tk.BooleanVar(value=True)
        tk.Checkbutton(config_grid, text="Usar todos los disponibles", variable=self.var_use_all_suicide,
                       bg="#16213e", fg="white", command=self.toggle_suicide_count).grid(row=0, column=1)
        
        tk.Label(config_grid, text="Cantidad:", bg="#16213e", fg="white").grid(row=0, column=2)
        self.entry_mix_suicide = tk.Entry(config_grid, width=8)
        self.entry_mix_suicide.insert(0, "22")
        self.entry_mix_suicide.grid(row=0, column=3)
        
        # Promo
        tk.Label(config_grid, text="Videos PROMO:", bg="#16213e", fg="#00d9ff", 
                 font=("Arial", 10, "bold")).grid(row=1, column=0, padx=5, pady=5)
        
        self.var_use_all_promo = tk.BooleanVar(value=True)
        tk.Checkbutton(config_grid, text="Usar todos los disponibles", variable=self.var_use_all_promo,
                       bg="#16213e", fg="white", command=self.toggle_promo_count).grid(row=1, column=1)
        
        tk.Label(config_grid, text="Cantidad:", bg="#16213e", fg="white").grid(row=1, column=2)
        self.entry_mix_promo = tk.Entry(config_grid, width=8)
        self.entry_mix_promo.insert(0, "24")
        self.entry_mix_promo.grid(row=1, column=3)
        
        # Botón crear mezcla
        tk.Button(config_grid, text="🎬 CREAR MEZCLA", command=self.create_mix,
                  bg="#e94560", fg="white", font=("Arial", 12, "bold")).grid(row=2, column=0, columnspan=4, pady=15)
        
        # Resultado
        result_frame = tk.LabelFrame(main_frame, text="📋 Resultado de la Mezcla", 
                                      bg="#16213e", fg="white", font=("Arial", 11, "bold"))
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.mix_result_text = tk.Text(result_frame, height=20, bg="#0f3460", fg="white")
        self.mix_result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    # ==================== FUNCIONES DE LÓGICA ====================
    
    def refresh_inventory_display(self):
        """Actualizar显示 del inventario"""
        inv = self.get_inventory()
        
        self.inventory_text.delete(1.0, tk.END)
        self.inventory_text.insert(tk.END, f"📊 INVENTARIO ACTUAL\n")
        self.inventory_text.insert(tk.END, f"{'='*50}\n\n")
        self.inventory_text.insert(tk.END, f"💀 Videos SUICIDE: {inv['SUICIDE']['total']} archivos\n")
        self.inventory_text.insert(tk.END, f"   📁 Ubicación: {os.path.join(SOURCE_ROOT, 'suicide')}\n\n")
        self.inventory_text.insert(tk.END, f"📸 Videos PROMO: {inv['PROMO']['total']} archivos\n")
        self.inventory_text.insert(tk.END, f"   📁 Ubicación: {os.path.join(SOURCE_ROOT, 'promo')}\n\n")
        self.inventory_text.insert(tk.END, f"📅 Días configurados: {len([d for d in os.listdir(OUTPUT_ROOT) if os.path.isdir(os.path.join(OUTPUT_ROOT, d))])}\n")
        
        self.update_stats()
        
    def update_stats(self):
        """Actualizar estadísticas"""
        inv = self.get_inventory()
        
        # Contar días
        days_count = 0
        if os.path.exists(OUTPUT_ROOT):
            days_count = len([d for d in os.listdir(OUTPUT_ROOT) if os.path.isdir(os.path.join(OUTPUT_ROOT, d))])
        
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, f"📈 ESTADÍSTICAS DEL SISTEMA\n")
        self.stats_text.insert(tk.END, f"{'='*50}\n\n")
        self.stats_text.insert(tk.END, f"👥 Cuentas Promo: {len(self.accounts_promo)}\n")
        self.stats_text.insert(tk.END, f"👥 Cuentas Suicide: {len(self.accounts_suicide)}\n")
        self.stats_text.insert(tk.END, f"🎞️ Total Videos: {inv['SUICIDE']['total'] + inv['PROMO']['total']}\n")
        self.stats_text.insert(tk.END, f"📅 Días creados: {days_count}\n")
        self.stats_text.insert(tk.END, f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        
    def refresh_account_lists(self):
        """Actualizar listas de cuentas"""
        self.list_promo.delete(0, tk.END)
        for acc in self.accounts_promo:
            self.list_promo.insert(tk.END, acc)
            
        self.list_suicide.delete(0, tk.END)
        for acc in self.accounts_suicide:
            self.list_suicide.insert(tk.END, acc)
            
    def add_promo_account(self):
        """Agregar cuenta promo"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Agregar Cuenta Promo")
        dialog.geometry("300x120")
        dialog.configure(bg="#16213e")
        
        tk.Label(dialog, text="Nombre de cuenta:", bg="#16213e", fg="white").pack(pady=5)
        entry = tk.Entry(dialog, width=30)
        entry.pack(pady=5)
        
        def save():
            if entry.get().strip():
                self.accounts_promo.append(entry.get().strip())
                self.refresh_account_lists()
                dialog.destroy()
                
        tk.Button(dialog, text="Agregar", command=save, bg="#00d9ff", fg="black").pack(pady=5)
        
    def add_suicide_account(self):
        """Agregar cuenta suicide"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Agregar Cuenta Suicide")
        dialog.geometry("300x120")
        dialog.configure(bg="#16213e")
        
        tk.Label(dialog, text="Nombre de cuenta:", bg="#16213e", fg="white").pack(pady=5)
        entry = tk.Entry(dialog, width=30)
        entry.pack(pady=5)
        
        def save():
            if entry.get().strip():
                self.accounts_suicide.append(entry.get().strip())
                self.refresh_account_lists()
                dialog.destroy()
                
        tk.Button(dialog, text="Agregar", command=save, bg="#e94560", fg="white").pack(pady=5)
        
    def remove_promo_account(self):
        """Eliminar cuentas promo seleccionadas"""
        selection = self.list_promo.curselection()
        for i in reversed(selection):
            self.accounts_promo.pop(i)
        self.refresh_account_lists()
        
    def remove_suicide_account(self):
        """Eliminar cuentas suicide seleccionadas"""
        selection = self.list_suicide.curselection()
        for i in reversed(selection):
            self.accounts_suicide.pop(i)
        self.refresh_account_lists()
        
    def toggle_suicide_count(self):
        """Alternar entrada de cantidad suicide"""
        if self.var_use_all_suicide.get():
            self.entry_mix_suicide.config(state='disabled')
        else:
            self.entry_mix_suicide.config(state='normal')
            
    def toggle_promo_count(self):
        """Alternar entrada de cantidad promo"""
        if self.var_use_all_promo.get():
            self.entry_mix_promo.config(state='disabled')
        else:
            self.entry_mix_promo.config(state='normal')
            
    def create_mix(self):
        """Crear mezcla de videos"""
        self.mix_result_text.delete(1.0, tk.END)
        self.mix_result_text.insert(tk.END, "🎬 CREANDO MEZCLA DE VIDEOS...\n")
        self.mix_result_text.insert(tk.END, "="*50 + "\n\n")
        
        inv = self.get_inventory()
        
        # Obtener cantidad
        suicide_count = inv['SUICIDE']['total'] if self.var_use_all_suicide.get() else int(self.entry_mix_suicide.get() or 0)
        promo_count = inv['PROMO']['total'] if self.var_use_all_promo.get() else int(self.entry_mix_promo.get() or 0)
        
        self.mix_result_text.insert(tk.END, f"📦 Videos Suicide: {suicide_count}\n")
        self.mix_result_text.insert(tk.END, f"📦 Videos Promo: {promo_count}\n\n")
        
        # Mezclar
        suicide_files = inv['SUICIDE']['files'].copy()
        promo_files = inv['PROMO']['files'].copy()
        
        random.shuffle(suicide_files)
        random.shuffle(promo_files)
        
        self.mix_result_text.insert(tk.END, "💀 VIDEOS SUICIDE SELECCIONADOS:\n")
        self.mix_result_text.insert(tk.END, "-"*40 + "\n")
        
        selected_suicide = suicide_files[:suicide_count]
        for i, f in enumerate(selected_suicide, 1):
            self.mix_result_text.insert(tk.END, f"  {i}. {f}\n")
            
        self.mix_result_text.insert(tk.END, "\n📸 VIDEOS PROMO SELECCIONADOS:\n")
        self.mix_result_text.insert(tk.END, "-"*40 + "\n")
        
        selected_promo = promo_files[:promo_count]
        for i, f in enumerate(selected_promo, 1):
            self.mix_result_text.insert(tk.END, f"  {i}. {f}\n")
            
        self.mix_result_text.insert(tk.END, f"\n✅ Mezcla creada con {len(selected_suicide) + len(selected_promo)} videos\n")
        
    def run_distribution(self):
        """Ejecutar distribución por días"""
        try:
            suicide_count = int(self.entry_suicide_count.get())
            promo_count = int(self.entry_promo_count.get())
            days = int(self.entry_days.get())
        except ValueError:
            messagebox.showerror("Error", "Por favor ingrese valores numéricos válidos")
            return
            
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, "🚀 INICIANDO DISTRIBUCIÓN...\n")
        self.preview_text.insert(tk.END, "="*50 + "\n\n")
        
        inv = self.get_inventory()
        
        suicide_files = inv['SUICIDE']['files'].copy()
        promo_files = inv['PROMO']['files'].copy()
        
        random.shuffle(suicide_files)
        random.shuffle(promo_files)
        
        for day in range(1, days + 1):
            self.preview_text.insert(tk.END, f"📅 Día {day}:\n")
            
            # Obtener videos para este día
            day_suicide = suicide_files[:suicide_count]
            day_promo = promo_files[:promo_count]
            
            # Quitar del pool
            suicide_files = suicide_files[suicide_count:]
            promo_files = promo_files[promo_count:]
            
            self.preview_text.insert(tk.END, f"   💀 Suicide: {len(day_suicide)} videos\n")
            self.preview_text.insert(tk.END, f"   📸 Promo: {len(day_promo)} videos\n\n")
            
        self.preview_text.insert(tk.END, "✅ Distribución completada (vista previa)\n")
        self.preview_text.insert(tk.END, "⚠️ Para ejecutar真正的 distribución, ejecute Organizador.py\n")


# ==================== INICIO ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramOrganizerGUI(root)
    root.mainloop()