from pipeline_simulator.core import memories, architectures, instructions, compilers
import logging
import sys


class Main:

    def run(self):
        # logging.basicConfig(stream=sys.stdout, level='INFO')
        source_file = 'tests/programs/code1.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers1.txt')
        memory = memories.Memory(2048)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        cpu_instance = architectures.PipelinedCpu(registers=registers, memory=memory, show_chronogram=True)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()


if __name__ == '__main__':
    Main().run()
