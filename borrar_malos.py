import pandas as pd

ruta = "data/lugares_limpio.csv"
df = pd.read_csv(ruta)
antes = len(df)

malos = (
    (df["nombre"].str.strip() == "Vips")
    | df["nombre"].str.contains("Sólo Salida", na=False)
    | df["nombre"].str.contains("Forum Buenavista", na=False)
)
print("Se van a borrar:")
print(df[malos][["id", "nombre", "categoria"]].to_string(index=False))

df = df[~malos]
df.to_csv(ruta, index=False, encoding="utf-8-sig")
print(f"\nLugares: {antes} -> {len(df)}")
