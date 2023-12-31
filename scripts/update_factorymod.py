# example usage:
# python3 scripts/update_factorymod.py --server "civclassic 2.0"

from argparse import ArgumentParser

import yaml

from civwiki_tools.utils import RESOURCES, relog
from civwiki_tools.factorymod import parse_factorymod, RecipeType, Factory, Config
from civwiki_tools import site

config_files = {
    "civcraft 3.0": RESOURCES / "civcraft 3.0.yaml",
    "civclassic 2.0": RESOURCES / "civclassic 2.0.yaml",
    "civmc": RESOURCES / "civmc.yaml"
}
# --server may be passed as e.g. civclassic 2.0, but the template page
# exists at CivClassic 2.0.
wiki_server_names = {
    "civcraft": "Civcraft",
    "civclassic": "CivClassic",
    "civmc": "CivMC"
}

# not sure where some of these servers got some of these names. Did "Oak Log"
# and "Oak Planks" really used to be called "Log" and "Wood"?
item_mappings = {
    # for civcraft 3.0
    "Log": "Oak Log",
    "Wood": "Oak Planks",
    "Ink Sack": "Ink Sac",
    "Grilled Pork": "Cooked Porkchop",
    "Thin Glass": "Glass Pane",
    "Wool": "White Wool",
    "Quartz Ore": "Nether Quartz Ore",
    "Sapling": "Oak Sapling",
    "Rails": "Rail",
    "Iron Fence": "Iron Bars",
    "Iron Spade": "Iron Shovel",
    "Diamond Spade": "Diamond Shovel",
    "Stone Spade": "Stone Shovel"
}

page_title = "Template:FactoryModConfig_{factory}_({server})"

def image(item_name):
    item_name = item_name.replace("_", " ").title()
    if item_name in item_mappings:
        item_name = item_mappings[item_name]
    return f"[[File:{item_name}.png|23px|middle]]"

def quantity_cell(quantities):
    # can happen for random outputs, where output is None but outputs is set
    if quantities is None:
        return "TODO"
    return ", ".join(f"{c.amount} {image(c.material)}" for c in quantities)

def fuel_cost(config, recipe):
    return recipe.production_time * config.default_fuel_consumption_intervall

def time_cell(recipe):
    return recipe.production_time

def fuel_cell(config, recipe):
    cost = fuel_cost(config, recipe)
    # TODO support displaying multiple default fuels, by cycling through them
    # in a gif. look at how minecraft.wiki does variable recipes
    return f"{cost} {image(config.default_fuel[0].material)}"

def repair_recipes(config, factory):
    repair_recipes = [r for r in factory.recipes if r.type is RecipeType.REPAIR]

    return "".join(f"""
        |-
        |{quantity_cell(r.input)}
        |{r.health_gained}
        |{time_cell(r)}
        |{fuel_cell(config, r)}""" for r in repair_recipes)

def recipes(config, factory):
    non_production_types = [RecipeType.UPGRADE, RecipeType.REPAIR]
    recipes = [r for r in factory.recipes if r.type not in non_production_types]
    return "".join(f"""
        |-
        |{r.name}
        |{quantity_cell(r.input)}
        |{quantity_cell(r.output)}
        |{time_cell(r)}
        |{fuel_cell(config, r)}""" for r in recipes)

def upgrades_from_to(config, factory):
    upgrades_from = config.upgrades_from[factory.name]
    upgrades_to = config.upgrades_to[factory.name]

    rows = []

    # number of upgrades to / from recipes might be imbalanced. Pad whichever
    # is lowest with {n/a} rows
    for i in range(max(len(upgrades_from), len(upgrades_to))):
        (r_from, f_from) = upgrades_from[i] if i < len(upgrades_from) else (None, None)
        (r_to, f_to) = upgrades_to[i] if i < len(upgrades_to) else (None, None)
        row = f"""
            |-
            |{f"{f_from.name}\n|{quantity_cell(r_from.input)}" if f_from else " colspan=\"2\" {{n/a}}"}
            |{f"{f_to.name}\n|{quantity_cell(r_to.input)}" if f_to else " colspan=\"2\" {{n/a}}"}
        """

        rows.append(row)

    table = """
        |-
        !Upgrades From
        !Cost
        !Upgrades To
        !Cost
    """.strip()
    if not rows:
        table += """
            |-
            | colspan=\"2\" {{n/a}}
            | colspan=\"2\" {{n/a}}"""
    table += "".join(rows)
    return table

# creation cost and repair recipes
def meta_table(config: Config, factory: Factory):
    return f"""
        {{| class="wikitable"
        |+
        ! colspan="4" |Creation Cost
        |-
        | colspan="4" {f"|{quantity_cell(factory.setupcost)}" if factory.setupcost else "{{n/a}}"}
        |-
        ! colspan="4" |Repair Cost
        |-
        !Cost
        !Health Repaired
        !Time
        !Fuel
        {repair_recipes(config, factory)}
        {upgrades_from_to(config, factory)}
        |}}
    """.strip()

def recipes_table(config: Config, factory: Factory):
    return f"""
        {{| class="wikitable"
        !Recipe
        !Input
        !Output
        !Time
        !Fuel
        {recipes(config, factory)}
        |}}
    """.strip()

def update_factory(config, factory, *, confirm=False, dry=False):
    meta_t = meta_table(config, factory)
    recipes_t = recipes_table(config, factory)
    new_text = f"{meta_t}\n\n{recipes_t}"

    # --server may be passed as e.g. civclassic 2.0, but the template page
    # exists at CivClassic 2.0.
    wiki_server_name = args.server
    for k, v in wiki_server_names.items():
        wiki_server_name = wiki_server_name.replace(k, v)

    title = page_title.format(factory=factory.name, server=wiki_server_name)
    page = site.page(title)
    title = page.title()

    if page.text == new_text:
        print(f"Nothing has changed for {title}. Skipping update")
        return

    if confirm:
        y_n = input(f"update {title}? y/n ")
        if y_n.lower() != "y":
            print(f"skipped {title}")
            return

    page.text = new_text

    if dry:
        print(page.text)
        return

    while True:
        try:
            page.save()
            return
        except Exception as e:
            print(f"ignoring exception {e}. Relogging...")
            relog()

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--factory", required=True)
    parser.add_argument("--dry", action="store_true", default=False)
    args = parser.parse_args()

    if args.server not in config_files:
        raise ValueError(f"invalid server {args.server}. Expected one of "
            f"{list(config_files.keys())}")

    config_file = config_files[args.server]
    with open(config_file) as f:
        data = yaml.safe_load(f)

    config = parse_factorymod(data)
    if args.factory == "all":
        factories = config.factories
    else:
        factories = [f for f in config.factories if f.name == args.factory]
        if not factories:
            raise ValueError(f"no factory named {args.factory}. Expected one of "
                f"{[f.name for f in config.factories]}")

    for factory in factories:
        update_factory(config, factory, dry=args.dry)
