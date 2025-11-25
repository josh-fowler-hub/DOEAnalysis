def is_valid(row):
    # row is a list in the order of factor_names as parsed from generate_pairwise_doe.py
    # This example disallows (Jacket Thickness == 2) with (Water Outlet == 125)
    try:
        if float(row[1]) == 2 and float(row[3]) == 125:
            return False
    except Exception:
        return True
    return True
