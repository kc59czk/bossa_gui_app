from tkinter import Tk, Label, Button, Text, Scrollbar, END, messagebox, Frame, StringVar
from bossa_api_client import BossaAPIClient
import sys

ACCOUNT_ID = "00-22-172137"
MONITORED_TICKER = "FW20U2520"

class BossaGUI:
    def __init__(self, master):
        self.master = master
        master.title("Bossa API Client")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        # Main frame for padding and resizing
        self.frame = Frame(master)
        self.frame.grid(sticky="nsew", padx=10, pady=10)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(6, weight=1)

        # Cash summary label (PLN)
        self.cash_var = StringVar()
        self.cash_var.set("Gotówka (PLN): -")
        self.label_cash = Label(self.frame, textvariable=self.cash_var, font=("Arial", 12, "bold"))
        self.label_cash.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        # SecValueSum summary label
        self.sec_value_sum_var = StringVar()
        self.sec_value_sum_var.set("SecValueSum: -")
        self.label_sec_value_sum = Label(self.frame, textvariable=self.sec_value_sum_var, font=("Arial", 12, "bold"))
        self.label_sec_value_sum.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        # Portfolio value summary label
        self.portfolio_value_var = StringVar()
        self.portfolio_value_var.set("Wartość portfela: -")
        self.label_portfolio_value = Label(self.frame, textvariable=self.portfolio_value_var, font=("Arial", 12, "bold"))
        self.label_portfolio_value.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Monitored ticker price label
        self.ticker_price_var = StringVar()
        self.ticker_price_var.set(f"{MONITORED_TICKER}: -")
        self.label_ticker_price = Label(self.frame, textvariable=self.ticker_price_var, font=("Arial", 12, "bold"))
        self.label_ticker_price.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.button_load = Button(self.frame, text="Pobierz portfel", command=self.load_portfolio)
        self.button_load.grid(row=4, column=0, pady=(0, 10), sticky="ew")

        self.button_exit = Button(self.frame, text="Zamknij", command=self.exit_app)
        self.button_exit.grid(row=4, column=1, pady=(0, 10), sticky="ew")

        self.text_portfolio = Text(self.frame, wrap='word', height=15, width=50)
        self.text_portfolio.grid(row=5, column=0, sticky="nsew")

        self.scrollbar = Scrollbar(self.frame, command=self.text_portfolio.yview)
        self.scrollbar.grid(row=5, column=1, sticky="ns")
        self.text_portfolio['yscrollcommand'] = self.scrollbar.set

        self.client = BossaAPIClient(username="BOS", password="BOS")

    def load_portfolio(self):
        if self.client.connect_and_login():
            portfolio_data = self.client.get_portfolio_state()
            # Only keep the selected account
            account_data = {ACCOUNT_ID: portfolio_data[ACCOUNT_ID]} if portfolio_data and ACCOUNT_ID in portfolio_data else {}
            self.display_portfolio(account_data)
            self.display_summary(account_data)
            self.display_ticker_price(account_data)
        else:
            messagebox.showerror("Błąd logowania", "Nie udało się zalogować.")

    def display_portfolio(self, portfolio_data):
        self.text_portfolio.delete(1.0, END)
        if portfolio_data:
            for account, data in portfolio_data.items():
                self.text_portfolio.insert(END, f"[ RACHUNEK: {account} ]\n")
                self.text_portfolio.insert(END, "  Środki:\n")
                for fund, value in data['funds'].items():
                    self.text_portfolio.insert(END, f"    - {fund}: {value}\n")
                self.text_portfolio.insert(END, "  Pozycje:\n")
                if data['positions']:
                    for pos in data['positions']:
                        self.text_portfolio.insert(END, f"    - Symbol: {pos['symbol']}, Ilość: {pos['quantity']}, ISIN: {pos['isin']}\n")
                else:
                    self.text_portfolio.insert(END, "    - Brak otwartych pozycji.\n")
        else:
            self.text_portfolio.insert(END, f"Brak danych dla rachunku {ACCOUNT_ID}.\n")

    def display_summary(self, portfolio_data):
        total_cash = 0.0
        total_sec_value_sum = 0.0
        total_portfolio_value = 0.0
        if portfolio_data:
            for data in portfolio_data.values():
                funds = data.get('funds', {})
                # Gotówka (PLN)
                cash = funds.get('PLN', 0)
                try:
                    total_cash += float(str(cash).replace(',', '.'))
                except Exception:
                    pass
                # SecValueSum
                sec_value_sum = funds.get('SecValueSum', 0)
                try:
                    total_sec_value_sum += float(str(sec_value_sum).replace(',', '.'))
                except Exception:
                    pass
                # Wartość portfela (PortfolioValue)
                portfolio_value = funds.get('PortfolioValue', 0)
                try:
                    total_portfolio_value += float(str(portfolio_value).replace(',', '.'))
                except Exception:
                    pass
        self.cash_var.set(f"Gotówka (PLN): {total_cash:.2f}")
        self.sec_value_sum_var.set(f"SecValueSum: {total_sec_value_sum:.2f}")
        self.portfolio_value_var.set(f"Wartość portfela: {total_portfolio_value:.2f}")

    def display_ticker_price(self, portfolio_data):
        # Szuka pozycji z tickerem MONITORED_TICKER i wyświetla jej cenę (jeśli jest)
        price = "-"
        if portfolio_data:
            for data in portfolio_data.values():
                for pos in data.get('positions', []):
                    if pos.get('symbol') == MONITORED_TICKER:
                        price = pos.get('price', '-')
                        break
        self.ticker_price_var.set(f"{MONITORED_TICKER}: {price}")

    def exit_app(self):
        self.master.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = Tk()
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    gui = BossaGUI(root)
    root.mainloop()