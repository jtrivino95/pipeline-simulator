from pipeline_simulator.core import memories, architectures, instructions
import logging
import sys


class Main:

    def run(self):
        logging.basicConfig(stream=sys.stdout, level='INFO')
        show_chronogram = False

        source_file = 'tests/programs/code1.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers1.txt')
        memory = memories.Memory(1024)
        parser = instructions.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        cpu_instance = architectures.PipelinedCpu(
            registers=registers, memory=memory, phase_cycles=[1, 1, 1, 1, 1],
            show_chronogram=show_chronogram)

        memory.set(99, 0)
        memory.set(100, 0)
        memory.set(101, 0)
        memory.set(102, 0)
        memory.set(103, 0)
        memory.set(104, 0)
        memory.set(1021, 0)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()


if __name__ == '__main__':
    Main().run()
