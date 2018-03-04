import logging
import sys
from .core import cpu, memories, instructions

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    source_file = sys.argv[1]
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    registers = memories.RegisterSet()
    memory = memories.Memory(2048)
    parser = instructions.Parser(registers=registers, memory=memory)
    program = parser.parse(source_file)
    memory.write_program(program)
    cpu_instance = cpu.Cpu(registers=registers, memory=memory)

    registers.get(0).set(0)
    registers.get(1).set(1)
    registers.get(11).set(11)

    cpu_instance.start()
    while not cpu_instance.is_halted():
        cpu_instance.step()

    logger.info("Cycles: %d" % cpu._statistics['cycles'])
    logger.info("Instructions: %d" % cpu._statistics['instructions'])
    logger.info("CPI: %f" % (cpu._statistics['cycles'] / cpu._statistics['instructions']))