import sys


def hazard(prev, current):
    if prev is None or current is None:
        return False
    # Only loads create the stall 
    if prev[0] != 'L':
        return False
    prev_dest = prev[1]
    if prev_dest == '0':
        return False
    # R instruction: R,dest,src1,src2
    if current[0] == 'R':
        return current[2] == prev_dest or current[3] == prev_dest
    # I instruction: I,dest,src,imm
    if current[0] == 'I':
        return current[2] == prev_dest
    # L instruction: L,dest,imm,base
    if current[0] == 'L':
        return current[3] == prev_dest
    # S instruction: S,src,imm,base
    if current[0] == 'S':
        return current[3] == prev_dest
    return False


def the_pipeline(instructions):
    output = []
    cycle = 0
    prev_instruction = None
    stall = 0
    for instruct in instructions:
        # Check if stall is needed
        if hazard(prev_instruction, instruct):
            stall = 1
        else:
            stall = 0
        # Five pipeline stages
        fetch = cycle
        decode = fetch + 1 + stall
        execute = decode + 1
        memory = execute + 1
        writeback = memory + 1
        output.append(
            f"{fetch:02},{decode:02},{execute:02},{memory:02},{writeback:02}")
        prev_instruction = instruct
        cycle += 1 + stall
    return output


def main():
    input_file = sys.argv[1]
    output_file = "out.txt"
    instructions = []
    with open(input_file, 'r') as file:
        instructions = [line.strip().split(',') for line in file]
    output = the_pipeline(instructions)
    with open(output_file, 'w') as file:
        file.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
