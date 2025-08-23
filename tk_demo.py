import tkinter as tk

root = tk.Tk()
root.title("pack() demo")

# Frame 1: only padx/pady
f1 = tk.Frame(root, bg="lightblue")
f1.pack(padx=20, pady=10)  # margins around
tk.Label(f1, text="padx=20, pady=10").pack()

# Frame 2: fill="x"
f2 = tk.Frame(root, bg="lightgreen")
f2.pack(fill="x", pady=5)
tk.Label(f2, text='fill="x" (stretches horizontally)').pack()

# Frame 3: expand=True
f3 = tk.Frame(root, bg="lightyellow")
f3.pack(expand=True, pady=5)
tk.Label(f3, text="expand=True (takes free space)").pack()

# Frame 4: fill="both", expand=True
f4 = tk.Frame(root, bg="lightcoral")
f4.pack(fill="both", expand=True, padx=10, pady=10)
tk.Label(f4, text='fill="both", expand=True').pack()

root.mainloop()
