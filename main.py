import os

class NexusException(Exception):
    pass

class NexusSyntaxError(NexusException, SyntaxError):
    pass

class NexusRuntimeError(NexusException, RuntimeError):
    pass

def execute_command(command, context_globals, last_condition_met=None, file_name=None, line_number=None):
    command = command.strip()
    if not command or command.startswith("#"):
        return "comment", context_globals, last_condition_met
    if command.lower().startswith("exit"):
        return "exit", context_globals, last_condition_met

    try:
        if command.startswith("ask("):
            prompt_text = command[len("ask("):command.rfind(")")].strip('"')
            user_value = input(prompt_text)
            context_globals['answer'] = user_value
            return "success", context_globals, None

        elif command.startswith("say("):
            echo_expression = command[len("say("):command.rfind(")")].strip()
            echo_text = eval(echo_expression, {}, context_globals)
            print(echo_text)
            return "success", context_globals, last_condition_met

        elif command.startswith("let "):
            var_name, value = command[len("let "):].split(" be ")
            var_name = var_name.strip()
            value = value.strip()
            if value.startswith("ask(") and value.endswith(")"):
                prompt_text = value[len("ask("):-1].strip('"').strip("'")
                user_value = input(prompt_text)
                context_globals[var_name] = user_value
            else:
                context_globals[var_name] = eval(value, {}, context_globals)
            return "success", context_globals, last_condition_met

        elif command.startswith("fn "):
            fn_def = command[len("fn "):].split(":", 1)
            function_signature = fn_def[0].strip()
            function_body = fn_def[1].strip() if len(fn_def) > 1 else ""
            function_name, *parameters = function_signature.split("(")
            parameters = parameters[0].rstrip(")").strip() if parameters else ""
            parameters = [param.strip() for param in parameters.split(",")] if parameters else []

            if not function_body.endswith("fn.end"):
                while True:
                    next_line = input().strip()
                    function_body += " " + next_line
                    if next_line.endswith("fn.end"):
                        break

            function_body = function_body[:-1].strip()
            context_globals[function_name.strip()] = (parameters, function_body)
            return "success", context_globals, last_condition_met

        elif command.startswith("call "):
            call_signature = command[len("call "):].strip().rstrip(";")
            function_name, *args = call_signature.split("(")
            args = args[0].rstrip(")").strip() if args else ""
            args = [eval(arg.strip(), {}, context_globals) for arg in args.split(",")] if args else []

            if function_name.strip() in context_globals:
                parameters, function_body = context_globals[function_name.strip()]
                if len(parameters) != len(args):
                    raise NexusRuntimeError(f"Function '{function_name.strip()}' expects {len(parameters)} arguments, but {len(args)} were given.")
                local_context = context_globals.copy()
                local_context.update(zip(parameters, args))
                lines = function_body.split(";")
                for line in lines:
                    if line.strip():
                        execute_command(line.strip() + ";", local_context, last_condition_met, file_name, line_number)
                context_globals.update(local_context)
                return "success", context_globals, last_condition_met
            else:
                raise NexusRuntimeError(f"Function '{function_name.strip()}' not defined.")

        elif command.startswith("module "):
            module_name = command[len("module "):].strip()
            module_file = f"{module_name}.nx"
            if not os.path.exists(module_file):
                raise NexusRuntimeError(f"Module file '{module_file}' not found.")
            with open(module_file, 'r') as file:
                file_commands = file.read().splitlines()
            i = 0
            while i < len(file_commands):
                line = file_commands[i].strip()
                if line.startswith("while ") and " do:" in line:
                    condition_action, i = read_multi_line_command(file_commands, i + 1, "while.end")
                    line = f"{line} {condition_action}"
                elif line.startswith("for ") and " do:" in line:
                    condition_action, i = read_multi_line_command(file_commands, i + 1, "for.end")
                    line = f"{line} {condition_action}"
                if line.startswith("fn ") and ":" in line and "fn.end" not in line:
                    function_definition = line
                    i += 1
                    while i < len(file_commands) and "}" not in file_commands[i]:
                        function_definition += " " + file_commands[i].strip()
                        i += 1
                    if i < len(file_commands):
                        function_definition += " " + file_commands[i].strip()
                    response, context_globals, last_condition_met = execute_command(function_definition,
                                                                                    context_globals,
                                                                                    last_condition_met,
                                                                                    module_file,
                                                                                    i + 1)
                else:
                    response, context_globals, last_condition_met = execute_command(line, context_globals,
                                                                                    last_condition_met,
                                                                                    module_file,
                                                                                    i + 1)
                if response == "exit":
                    return "exit", context_globals, last_condition_met
                i += 1
            return "success", context_globals, last_condition_met

        elif "if " in command:
            condition, action = command[3:].split(" then ")
            condition_met = eval(condition, {}, context_globals)
            if condition_met:
                _, context_globals, _ = execute_command(action + ";", context_globals, last_condition_met, file_name,
                                                        line_number)
            return "success", context_globals, condition_met

        elif "elif " in command:
            if last_condition_met is not None and not last_condition_met:
                condition, action = command[5:].split(" then ")
                condition_met = eval(condition, {}, context_globals)
                if condition_met:
                    _, context_globals, _ = execute_command(action + ";", context_globals, last_condition_met,
                                                            file_name, line_number)
                return "success", context_globals, condition_met

        elif "else" in command:
            action = command[5:].strip()
            if last_condition_met is not None and not last_condition_met:
                _, context_globals, _ = execute_command(action + ";", context_globals, last_condition_met, file_name,
                                                        line_number)
            return "success", context_globals, last_condition_met

        elif command.startswith("while "):
            parts = command[6:].split(" do:", 1)
            condition = parts[0].strip()
            action = parts[1].strip()
            while eval(condition, {}, context_globals):
                response, context_globals, last_condition_met = execute_command(action, context_globals, last_condition_met, file_name, line_number)
                if response == "exit":
                    return "exit", context_globals, last_condition_met
            return "success", context_globals, last_condition_met

        elif command.startswith("for "):
            parts = command[4:].split(" in ")
            var_name = parts[0].strip()
            iterable = eval(parts[1].split(" do:", 1)[0].strip(), {}, context_globals)
            action = parts[1].split(" do:", 1)[1].strip()
            for item in iterable:
                context_globals[var_name] = item
                response, context_globals, last_condition_met = execute_command(action, context_globals, last_condition_met, file_name, line_number)
                if response == "exit":
                    return "exit", context_globals, last_condition_met
            return "success", context_globals, last_condition_met

        else:
            raise NexusSyntaxError(f"Command '{command}' not recognized.")

    except Exception as e:
        error_message = f"Error: {str(e)}"
        if file_name:
            error_message += f" -> {file_name}"
            if line_number:
                error_message += f":{line_number}"
        print("\033[91m{}\033[0m".format(error_message))
        return "error", context_globals, last_condition_met

    return "success", context_globals, last_condition_met

def read_multi_line_command(lines, i, end_keyword):
    command_body = ""
    while i < len(lines):
        line = lines[i].strip()
        if line == end_keyword:
            break
        command_body += line + " "
        i += 1
    return command_body.strip(), i

def main():
    context_globals = {}
    last_condition_met = None
    while True:
        print("Nexus (" + os.path.realpath(__file__) + ") -> ")
        user_input = input().strip()
        if user_input.lower().startswith("run "):
            file_path = user_input[len("run "):].strip()
            if file_path.endswith(".nx") and os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    file_commands = file.read().splitlines()
                i = 0
                while i < len(file_commands):
                    line = file_commands[i].strip()
                    if line.startswith("while ") and " do:" in line:
                        condition_action, i = read_multi_line_command(file_commands, i + 1, "while.end")
                        line = f"{line} {condition_action}"
                    elif line.startswith("for ") and " do:" in line:
                        condition_action, i = read_multi_line_command(file_commands, i + 1, "for.end")
                        line = f"{line} {condition_action}"
                    if line.startswith("fn ") and ":" in line and "fn.end" not in line:
                        function_definition = line
                        i += 1
                        while i < len(file_commands) and "}" not in file_commands[i]:
                            function_definition += " " + file_commands[i].strip()
                            i += 1
                        if i < len(file_commands):
                            function_definition += " " + file_commands[i].strip()
                        response, context_globals, last_condition_met = execute_command(function_definition,
                                                                                        context_globals,
                                                                                        last_condition_met,
                                                                                        file_path,
                                                                                        i + 1)
                    else:
                        response, context_globals, last_condition_met = execute_command(line, context_globals,
                                                                                        last_condition_met,
                                                                                        file_path,
                                                                                        i + 1)
                    if response == "exit":
                        return
                    i += 1
            else:
                print("Invalid file type or file not found. Please use a '.nx' file.")
            continue
        response, context_globals, last_condition_met = execute_command(user_input, context_globals, last_condition_met)

        if response == "exit":
            break

if __name__ == "__main__":
    main()