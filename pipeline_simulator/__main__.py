import sys
from .core import memories, cpu, instructions


if __name__ == '__main__':
    source_file = sys.argv[1]
    registers_config = 'registers.ini'
    registers = memories.RegisterSet()
    memory = memories.Memory(1024)
    parser = instructions.Parser(registers=registers, memory=memory)
    program = parser.parse(source_file)