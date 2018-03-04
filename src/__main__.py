import logging
import sys
from .core import cpu, memories, instructions


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    source_file = 'code.txt'
    registers = memories.RegisterSet()
    memory = memories.Memory(1024)

    parser = instructions.Parser(registers=registers, memory=memory)
    program = parser.parse(source_file)
    memory.write_program(program)
    cpu = cpu.Cpu(registers=registers, memory=memory)

    regvalues = [0, 91, 1, 3, 31, 100, 100, 100]
    for i, val in enumerate(regvalues):
        registers.get(i).set(val)

    cpu.start()
    while not cpu.is_halted():
        cpu.step()

    for i in range(8):
        print(str(registers.get(i)) + ': ' + str(registers.get(i).get_data()))
