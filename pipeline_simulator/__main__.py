from pipeline_simulator.core import memories, architectures, instructions, compilers
import logging
import sys


class Main:

    def run(self):
        """
        Test if parser creates correct Instruction and Register instances
        """

        source_file = 'tests/programs/code1.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers1.txt')
        memory = memories.Memory(1024)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)


if __name__ == '__main__':
    Main().run()
