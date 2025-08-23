import tkinter as tk

def on_resize(event, name):
    print(f"{name} resized: width={event.width}, height={event.height}")

root = tk.Tk()
root.title("grid() resize demo")
root.geometry("500x400")

# Configure root grid so rows/columns can expand
root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)
root.grid_rowconfigure(2, weight=1)
root.grid_rowconfigure(3, weight=1)
root.grid_columnconfigure(0, weight=1)

# Frame 1: only padding
f1 = tk.Frame(root, bg="lightblue")
f1.grid(row=0, column=0, padx=20, pady=10, sticky="")
tk.Label(f1, text="padx=20, pady=10").pack()
f1.bind("<Configure>", lambda e: on_resize(e, "Frame1"))

# Frame 2: sticky="ew" (east-west)
f2 = tk.Frame(root, bg="lightgreen")
f2.grid(row=1, column=0, pady=5, sticky="ew")
tk.Label(f2, text='sticky="ew" (stretches horizontally)').pack()
f2.bind("<Configure>", lambda e: on_resize(e, "Frame2"))

# Frame 3: sticky="ns" (north-south)
f3 = tk.Frame(root, bg="lightyellow")
f3.grid(row=2, column=0, pady=5, sticky="ns")
tk.Label(f3, text='sticky="ns" (stretches vertically)').pack()
f3.bind("<Configure>", lambda e: on_resize(e, "Frame3"))

# Frame 4: sticky="nsew" (all directions)
f4 = tk.Frame(root, bg="lightcoral")
f4.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
tk.Label(f4, text='sticky="nsew" (fills all space)').pack()
f4.bind("<Configure>", lambda e: on_resize(e, "Frame4"))

root.mainloop()
