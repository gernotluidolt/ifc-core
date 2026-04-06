from pathlib import Path

from loguru import logger

from ifc_core import IfcStore


def main():
    # Replace 'test.ifc' with a real file path to test
    try:
        store = IfcStore(Path(r"C:\Users\User\Desktop\BMW.ifc"))
        logger.info(
            f"Loaded {store.info.schema_version} model by {store.info.author} full of metadata: {store.info}"
        )
    except FileNotFoundError:
        logger.warning(
            "Setup complete! Please provide a test.ifc file to run the full check."
        )


if __name__ == "__main__":
    main()
