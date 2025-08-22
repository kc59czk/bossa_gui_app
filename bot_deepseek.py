import tkinter as tk
from tkinter import ttk, messagebox
import random
from datetime import datetime

class ScalpingBot:
    def __init__(self):
        self.commission = 2  # 2 points commission per trade
        self.daily_goal = 20  # 20 points daily goal
        self.current_profit = 0
        self.trades = []
        self.is_running = False
        self.balance = 10000  # Starting balance
        self.contract_size = 1  # Trading 1 future contract
        
    def calculate_profit(self, entry_price, exit_price, quantity, is_long):
        # Calculate profit considering commission
        price_diff = exit_price - entry_price if is_long else entry_price - exit_price
        profit = price_diff * quantity - self.commission
        return profit

class ScalpingBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Warsaw Stock Exchange Scalping Bot")
        self.root.geometry("900x700")
        self.root.configure(bg='#2c3e50')
        
        # Initialize bot and current price
        self.bot = ScalpingBot()
        self.current_price = 4500.0  # Initialize current_price here
        
        # Create notebook (tab container)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create frames for tabs
        self.create_dashboard_tab()
        self.create_trading_tab()
        self.create_settings_tab()
        self.create_logs_tab()
        
        # Start price simulation
        self.update_price()
        
    def create_dashboard_tab(self):
        # Create frame for dashboard tab
        dashboard_frame = ttk.Frame(self.notebook, padding="10")
        dashboard_frame.pack(fill='both', expand=True)
        
        # Dashboard title
        title_label = ttk.Label(dashboard_frame, text="Trading Dashboard", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Performance Metrics", padding="10")
        stats_frame.pack(fill='x', pady=10)
        
        # Stats labels
        ttk.Label(stats_frame, text="Current Balance:").grid(row=0, column=0, sticky='w', pady=5)
        self.balance_var = tk.StringVar(value=f"${self.bot.balance:,.2f}")
        ttk.Label(stats_frame, textvariable=self.balance_var, font=('Arial', 12, 'bold')).grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Today's Profit:").grid(row=1, column=0, sticky='w', pady=5)
        self.profit_var = tk.StringVar(value=f"{self.bot.current_profit} points")
        ttk.Label(stats_frame, textvariable=self.profit_var, font=('Arial', 12, 'bold')).grid(row=1, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Daily Goal:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Label(stats_frame, text=f"{self.bot.daily_goal} points", font=('Arial', 12)).grid(row=2, column=1, sticky='w', pady=5)
        
        ttk.Label(stats_frame, text="Commission:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Label(stats_frame, text=f"{self.bot.commission} points per trade", font=('Arial', 12)).grid(row=3, column=1, sticky='w', pady=5)
        
        # Progress towards goal
        ttk.Label(stats_frame, text="Goal Progress:").grid(row=4, column=0, sticky='w', pady=5)
        self.progress = ttk.Progressbar(stats_frame, orient='horizontal', length=200, mode='determinate')
        self.progress.grid(row=4, column=1, sticky='w', pady=5)
        self.update_progress()
        
        # Current price frame
        price_frame = ttk.LabelFrame(dashboard_frame, text="Current Price", padding="10")
        price_frame.pack(fill='x', pady=10)
        
        ttk.Label(price_frame, text="FUTURES INDEX:").grid(row=0, column=0, sticky='w', pady=5)
        self.price_var = tk.StringVar(value=f"{self.current_price:.2f}")
        price_label = ttk.Label(price_frame, textvariable=self.price_var, font=('Arial', 20, 'bold'))
        price_label.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        
        self.price_change_var = tk.StringVar(value="→")
        self.price_change_label = ttk.Label(price_frame, textvariable=self.price_change_var, font=('Arial', 16))
        self.price_change_label.grid(row=0, column=2, sticky='w', pady=5)
        
        # Bot control frame
        control_frame = ttk.Frame(dashboard_frame)
        control_frame.pack(pady=20)
        
        self.start_button = ttk.Button(control_frame, text="Start Bot", command=self.toggle_bot)
        self.start_button.pack(side='left', padx=10)
        
        ttk.Button(control_frame, text="Reset Day", command=self.reset_day).pack(side='left', padx=10)
        
        # Add the frame to the notebook
        self.notebook.add(dashboard_frame, text="Dashboard")
        
    def create_trading_tab(self):
        # Create frame for trading tab
        trading_frame = ttk.Frame(self.notebook, padding="10")
        trading_frame.pack(fill='both', expand=True)
        
        # Trading title
        title_label = ttk.Label(trading_frame, text="Trading Parameters", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Strategy settings
        strategy_frame = ttk.LabelFrame(trading_frame, text="Trading Strategy", padding="10")
        strategy_frame.pack(fill='x', pady=10)
        
        ttk.Label(strategy_frame, text="Entry Threshold (points):").grid(row=0, column=0, sticky='w', pady=5)
        self.entry_threshold = ttk.Entry(strategy_frame)
        self.entry_threshold.insert(0, "5")
        self.entry_threshold.grid(row=0, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(strategy_frame, text="Stop Loss (points):").grid(row=1, column=0, sticky='w', pady=5)
        self.stop_loss = ttk.Entry(strategy_frame)
        self.stop_loss.insert(0, "10")
        self.stop_loss.grid(row=1, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(strategy_frame, text="Take Profit (points):").grid(row=2, column=0, sticky='w', pady=5)
        self.take_profit = ttk.Entry(strategy_frame)
        self.take_profit.insert(0, "8")
        self.take_profit.grid(row=2, column=1, sticky='w', pady=5, padx=5)
        
        # Manual trade frame
        manual_frame = ttk.LabelFrame(trading_frame, text="Manual Trade", padding="10")
        manual_frame.pack(fill='x', pady=10)
        
        ttk.Button(manual_frame, text="BUY", command=lambda: self.manual_trade(True)).pack(side='left', padx=10)
        ttk.Button(manual_frame, text="SELL", command=lambda: self.manual_trade(False)).pack(side='left', padx=10)
        
        # Add the frame to the notebook
        self.notebook.add(trading_frame, text="Trading")
        
    def create_settings_tab(self):
        # Create frame for settings tab
        settings_frame = ttk.Frame(self.notebook, padding="10")
        settings_frame.pack(fill='both', expand=True)
        
        # Settings title
        title_label = ttk.Label(settings_frame, text="Bot Configuration", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Settings form
        form_frame = ttk.Frame(settings_frame)
        form_frame.pack(fill='both', expand=True, pady=10)
        
        ttk.Label(form_frame, text="Daily Goal (points):").grid(row=0, column=0, sticky='w', pady=10, padx=10)
        self.daily_goal_entry = ttk.Entry(form_frame)
        self.daily_goal_entry.insert(0, str(self.bot.daily_goal))
        self.daily_goal_entry.grid(row=0, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Label(form_frame, text="Commission (points):").grid(row=1, column=0, sticky='w', pady=10, padx=10)
        self.commission_entry = ttk.Entry(form_frame)
        self.commission_entry.insert(0, str(self.bot.commission))
        self.commission_entry.grid(row=1, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Label(form_frame, text="Contract Size:").grid(row=2, column=0, sticky='w', pady=10, padx=10)
        self.contract_size_entry = ttk.Entry(form_frame)
        self.contract_size_entry.insert(0, str(self.bot.contract_size))
        self.contract_size_entry.grid(row=2, column=1, sticky='w', pady=10, padx=10)
        
        ttk.Button(form_frame, text="Save Settings", command=self.save_settings).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Add the frame to the notebook
        self.notebook.add(settings_frame, text="Settings")
        
    def create_logs_tab(self):
        # Create frame for logs tab
        logs_frame = ttk.Frame(self.notebook, padding="10")
        logs_frame.pack(fill='both', expand=True)
        
        # Logs title
        title_label = ttk.Label(logs_frame, text="Trading Activity Log", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Log text area
        self.log_text = tk.Text(logs_frame, height=20, width=80, state='disabled')
        scrollbar = ttk.Scrollbar(logs_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Add the frame to the notebook
        self.notebook.add(logs_frame, text="Activity Log")
        
    def update_price(self):
        if hasattr(self, 'price_var'):
            # Simulate price changes
            change = random.uniform(-5, 5)
            self.current_price += change
            self.price_var.set(f"{self.current_price:.2f}")
            
            # Update change indicator
            if change > 0.1:
                self.price_change_var.set("↑")
                self.price_change_label.configure(foreground='green')
            elif change < -0.1:
                self.price_change_var.set("↓")
                self.price_change_label.configure(foreground='red')
            else:
                self.price_change_var.set("→")
                self.price_change_label.configure(foreground='gray')
            
            # Simulate trades if bot is running
            if self.bot.is_running:
                self.simulate_trade()
            
        # Schedule next update
        self.root.after(1000, self.update_price)
        
    def simulate_trade(self):
        # Simulate random trading decisions (in a real bot, this would be based on strategy)
        if random.random() < 0.3:  # 30% chance of making a trade each second
            is_long = random.random() < 0.5  # Randomly choose long or short
            entry_price = self.current_price
            exit_price = entry_price + random.uniform(2, 10) * (1 if is_long else -1)
            quantity = self.bot.contract_size
            
            profit = self.bot.calculate_profit(entry_price, exit_price, quantity, is_long)
            self.bot.current_profit += profit
            self.bot.balance += profit * 10  # Assuming 1 point = $10
            
            # Record trade
            trade = {
                'time': datetime.now().strftime("%H:%M:%S"),
                'type': 'LONG' if is_long else 'SHORT',
                'entry': entry_price,
                'exit': exit_price,
                'quantity': quantity,
                'profit': profit
            }
            self.bot.trades.append(trade)
            
            # Update UI
            self.update_progress()
            self.log_trade(trade)
            
            # Check if daily goal is reached
            if self.bot.current_profit >= self.bot.daily_goal:
                self.bot.is_running = False
                self.start_button.config(text="Start Bot")
                self.log_message("Daily goal reached! Bot stopped.")
                
    def manual_trade(self, is_long):
        entry_price = self.current_price
        # For simulation, assume a fixed exit price
        exit_price = entry_price + (5 if is_long else -5)
        quantity = self.bot.contract_size
        
        profit = self.bot.calculate_profit(entry_price, exit_price, quantity, is_long)
        self.bot.current_profit += profit
        self.bot.balance += profit * 10  # Assuming 1 point = $10
        
        # Record trade
        trade = {
            'time': datetime.now().strftime("%H:%M:%S"),
            'type': 'LONG' if is_long else 'SHORT',
            'entry': entry_price,
            'exit': exit_price,
            'quantity': quantity,
            'profit': profit
        }
        self.bot.trades.append(trade)
        
        # Update UI
        self.update_progress()
        self.log_trade(trade)
        
    def update_progress(self):
        # Update progress bar
        progress_percent = (self.bot.current_profit / self.bot.daily_goal) * 100
        self.progress['value'] = min(progress_percent, 100)
        
        # Update labels
        self.profit_var.set(f"{self.bot.current_profit:.2f} points")
        self.balance_var.set(f"${self.bot.balance:,.2f}")
        
    def log_trade(self, trade):
        self.log_message(
            f"{trade['time']} - {trade['type']} - "
            f"Entry: {trade['entry']:.2f} - "
            f"Exit: {trade['exit']:.2f} - "
            f"Profit: {trade['profit']:.2f} points"
        )
        
    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        
    def toggle_bot(self):
        self.bot.is_running = not self.bot.is_running
        if self.bot.is_running:
            self.start_button.config(text="Stop Bot")
            self.log_message("Bot started - beginning to scan for opportunities...")
        else:
            self.start_button.config(text="Start Bot")
            self.log_message("Bot stopped")
            
    def reset_day(self):
        self.bot.current_profit = 0
        self.bot.trades = []
        self.update_progress()
        self.log_message("Day reset - all profits and trades cleared")
        
    def save_settings(self):
        try:
            self.bot.daily_goal = int(self.daily_goal_entry.get())
            self.bot.commission = int(self.commission_entry.get())
            self.bot.contract_size = int(self.contract_size_entry.get())
            self.update_progress()
            self.log_message("Settings saved successfully")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for all settings")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScalpingBotApp(root)
    root.mainloop()