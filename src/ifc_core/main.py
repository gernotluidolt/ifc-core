from loguru import logger
import ifcopenshell

def main():
    logger.info("IFC-Core System Online.")
    # For now, let's just print the version of the library
    logger.debug(f"IfcOpenShell version: {ifcopenshell.__version__}")

if __name__ == "__main__":
    main()