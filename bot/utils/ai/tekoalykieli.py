def tulkitse_tekoalykieli(syote: str) -> tuple[str, str]:
    osat = syote.strip().split(" ", 1)
    if len(osat) != 2:
        raise ValueError("Virheellinen syntaksi. Käytä muotoa: KÄSKY kysymys")
    komento, argumentti = osat
    komento = komento.upper()
    if komento not in ["HAE", "KYSY", "GENEROI"]:
        raise ValueError(f"Tuntematon komento: {komento}")
    return komento, argumentti
