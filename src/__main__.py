import logging
from .core import cpu, memories, instructions


if __name__ == '__main__':
    logging.basicConfig(filename='debug.log', level=logging.INFO)
    source_file = 'code.txt'
    registers = memories.RegisterSet()
    memory = memories.Memory(1024)

    parser = instructions.Parser(registers=registers, memory=memory)
    program = parser.parse(source_file)
    memory.load_program(program)
    cpu = cpu.Cpu(registers=registers, memory=memory)

    regvalues = [5, 7, 3, 1, 6, 12, 18, 22]
    for i, val in enumerate(regvalues):
        registers.get(i).set(val)

    cpu.start()
    while not cpu.is_halted():
        try:
            cpu.step()
        except Exception as e:
            print(e)
            break

    for i in range(11):

        print(str(registers.get(i)) + ': ' + str(registers.get(i).get()))
