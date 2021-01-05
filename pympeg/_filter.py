"""
Creates complex and simple filters based on following functions
builds a chain of functions each containing a type of Node that
linked using the Label that identifies the stream and builds the
filter and is understandable by the ffmpeg command line.
"""

from subprocess import Popen, PIPE, STDOUT

from ._builder import Stream
from ._exceptions import *
from ._node import (InputNode, FilterNode, Label,
                    OptionNode, OutputNode, GlobalNode, stream)
from ._util import get_str_from_filter, get_str_from_global


__all__ = ["input", "filter", "output", "arg", "run", "graph", "option"]
s = Stream()


def _check_arg_type(args):
    """
    Only allow the following calling arguments to create a chain.
    The functions should be only callable by the following objects
    and the argument will be parsed as a node to create the chain.

    Parameters
    ----------
    args : list
        mostly caller of the function

    Returns
    -------
    bool
        passed/ fail criteria
    """
    flag = False

    for arg_ in args:
        if (
                isinstance(arg_, InputNode) or
                isinstance(arg_, OptionNode) or
                isinstance(arg_, FilterNode) or
                isinstance(arg_, GlobalNode) or
                isinstance(arg_, Label) or
                isinstance(arg_, list)
                ):
            flag = True
        break

    return flag


def _get_label_param(value):
    """
    Generate label based on the type of the object.
    This label gets added as the input to the node in
    the chain and creates a graph like structure.

    Parameters
    ----------
    value : object
        type of the object that is deduced below

    Returns
    -------
    Label
        label to link with the node from ip - > op
    """
    if isinstance(value, Label):
        return value

    if isinstance(value, str):
        return Label(value)

    if isinstance(value, FilterNode):
        return value[0]

    if isinstance(value, InputNode):
        return Label(value.outputs)

    if isinstance(value, GlobalNode):
        return value[0]

    else:
        raise TypeMissing("Filter requires an filter or input type argument")


def _get_nodes_from_graph(graph):
    """
    Separates the types of the nodes. Since, the links are
    directly attached to the node via the Label object and only
    the label matters at the end of the command, so distributing
    the nodes based on types helps create a command line argument.

    Parameters
    ----------
    graph : Sized, list-type
        output at the end of the run function. A list of all nodes

    Returns
    -------
    tuple
        distribution of all the nodes via their types
    """
    (
        input_nodes,
        option_nodes,
        filter_nodes,
        global_nodes, 
        output_nodes
            ) = (
                    list(), list(),
                    list(), list(),
                    list()
                )

    for node in graph:
        if isinstance(node, InputNode):
            input_nodes.append(node)

        if isinstance(node, FilterNode):
            filter_nodes.append(node)

        if isinstance(node, OutputNode):
            output_nodes.append(node)

        if isinstance(node, GlobalNode):
            global_nodes.append(node)

        if isinstance(node, OptionNode):
            option_nodes.append(node)

    node_len = len(input_nodes) + len(option_nodes) + len(filter_nodes) + len(global_nodes) + len(output_nodes)
    assert node_len == len(graph)

    return input_nodes, option_nodes, filter_nodes, global_nodes, output_nodes


def _no_filter_command(input_nodes, output_nodes, cmd="ffmpeg"):
    """
    Cases when there is no filter. Mostly when conversion is required.

    Example
    -------
    ex: convert .mp4 to .wav
        ffmpeg -y -i example.mp4 example.wav
    """
    result = list()

    result.append(cmd)
    result.append(" -y")
    for inp in input_nodes:
        result.append(" -i %s " % inp.name)

    for out in output_nodes:
        result.append(" %s " % out.name)
    return ''.join(result)


def _get_command_from_graph(graph, cmd="ffmpeg"):
    """
    Generates the command line for the graph, this command is
    then ran using subprocess which will raise any exception or
    error on the ffmpeg side.

    Parameters
    ----------
    graph : list-type
        nodes from the end of the run function
    cmd : str
        ffmpeg default command, may changed based on alias

    Returns
    -------
    str
        string of the command to execute.

    Raises
    -------
    FFmpegException
        raised when the subprocess function fails.
    """
    result = list()
    input_nodes, option_nodes, filter_nodes, global_nodes, output_nodes = _get_nodes_from_graph(graph)

    # means that there is no filter
    if len(filter_nodes) == 0:
        return _no_filter_command(input_nodes, output_nodes)

    last_filter_node = filter_nodes.pop()

    # adding input nodes in fiter
    result.append(cmd)
    for inp in input_nodes:
        result.append(" -i %s " % inp.name)

    # adding option nodes in filter
    for opt in option_nodes:
        result.append(" %s %s" % (opt.tag, opt.name))

    # adding filter nodes in filter
    result.append(' -y -filter_complex "')
    for filter_ in filter_nodes:
        result.append(get_str_from_filter(filter_))

    # adding global nodes
    for global_ in global_nodes:
        result.append(get_str_from_global(global_))

    # last filter should not have a semicolon at the end
    result.append(get_str_from_filter(last_filter_node).replace(";", ""))
    result.append('"')

    # multiple output nodes
    for out in output_nodes:
        for inp in out.inputs:
            result.append(' -map "[%s]"' % inp.label)
            result.append(" %s " % out.name)

    return ''.join(result)


@stream()
def input(*args, name):
    """
    Creates the input node. Can create multiple input nodes.
    Requires the named argument to execute.
            ffmpeg -i input_example.mp4 -i input.mp3 ...

    Parameters
    ----------
    
    name : str
        name and path of the file

    Returns
    -------
    InputNode
        returns the input type of the node, which can recall this function

    Raises
    -------
    InputParamsMissing
        when the named argument (name) is missing.
    """
    if name is None:
        raise InputParamsMissing("File name required in input function")

    # creating a file input filter
    node = InputNode(name, s.count)

    # adding to the stream
    s.add(node).count += 1

    return node


@stream()
def filter(*args, **kwargs):
    """
    Generates the filter based on the input caller, the input caller
    can be another filter node or any input node. Creates a Filter Node
    with input from the caller object.

    Parameters
    ----------
    args : list-type
            input args
    kwargs : dict-type
            name input args

    Returns
    -------
    FilterNode
            filter created for the input or another filter

    Raises
    -------
    TypeMissing
            caller is of some unknown type
    FilterParamsMissing
            filter was not able to create
    """
    if not _check_arg_type(args):
        raise TypeMissing("Filter requires an filter or input type argument")

    if len(kwargs) == 0:
        raise FilterParamsMissing

    # if explicit inputs are given skip caller
    if "inputs" in kwargs:
        inputs = kwargs["inputs"]
    # accept caller
    else:
        inputs = args[0]

    filter_node = FilterNode(**kwargs)

    if isinstance(inputs, list):
        for inp in inputs:
            filter_node.add_input(_get_label_param(inp))
    else:
        filter_node.add_input(_get_label_param(inputs))

    s.add(filter_node)
    return filter_node


@stream()
def output(*args, **kwargs):
    """
    Generates an OutputNode for the input filters or InputNodes
    The object gets parsed and the inputs are used for the map
    parameters in the ffmpeg command line

            ffmpeg .... -map "[label]" ... output.mp4

    Parameters
    ----------
    args : list-type
        input args
    kwargs : dict
        name input args

    Returns
    -------
    OutputNode
        output node for the filter or the input caller

    Raises
    -------
    TypeMissing
        caller is of some unknown type
    """
    if not _check_arg_type(args):
        raise TypeMissing("Output requires an filter or input type argument")

    if "name" not in kwargs:
        return None

    node = OutputNode(name=kwargs["name"])
    inputs = args[0]

    if isinstance(inputs, list):
        for inp in inputs:
            node.add_input(_get_label_param(inp))
    else:
        node.add_input(_get_label_param(inputs))

    s.add(node)
    return node


@stream()
def arg(caller=None, args=None, outputs=None, inputs=None):
    """
    Generates the GlobalNode for any filter types that cannot be
    created by the filter function. One of such filter is the concat.
    Other functions that do not follow the same syntax rules like filters.
    Then any function can be created and the command line argument can
    be directly stated using the names arguments (args), with inputs and outputs

    Examples
    --------
        inputs : [0:v][0:a][3:v][3:a]

        ffmpeg.arg(inputs=["0:v", "0:a", "3:v", "3:a"], outputs=["video", "audio"],
                     args="concat=2:a=1:v=1")

         OP: [0:v][0:a][3:v][3:a] concat=2:a=1:v=1 [video][audio];
    Parameters
    ----------
    caller : any
        input for the Global Node
    args : str
        complete command with arguments can have any structure
    outputs : any
        outputs for the Global Node
    inputs : any
        inputs for the Global Node

    Returns
    -------
    GlobalNode
        global node that can have any structure with predefined function attributes.
    """
    node = GlobalNode(args=args)

    # if inputs is there don't check caller
    if inputs is not None:
        if isinstance(inputs, list):
            for inp in inputs:
                node.add_input(_get_label_param(inp))
        else:
            node.add_input(_get_label_param(inputs))

    # if inputs is absent
    else:
        if isinstance(caller, list):
            for inp in caller:
                node.add_input(_get_label_param(inp))
        else:
            node.add_input(_get_label_param(caller))

    # adding outputs, if none then 1 output is created by default
    if isinstance(outputs, list):
        for out in outputs:
            node.add_output(_get_label_param(out))
    else:
        node.add_output(_get_label_param(outputs))

    s.add(node)
    return node


@stream()
def option(*args, tag=None, name=None, output=None):
    outputs = list()

    if isinstance(output, list):
        for out in output:
            outputs.append(_get_label_param(out))
    else:
        outputs.append(_get_label_param(output))

    node = OptionNode(tag, name, output)
    s.add(node)

    return node


@stream()
def run(caller):
    """
    Parses the entire chain of nodes, isolates the nodes based on types
    and generate a ffmpeg style command that will be run in the subprocess.
    Logs and errors are returned and final output can be created.

    Parameters
    ----------
    caller : OutputNode
            calling node, mostly an OutputNode

    Returns
    -------
    tuple
            log, error of just yield values
    """
    if not isinstance(caller, OutputNode):
        raise OutputNodeMissingInRun

    graph = s.graph()
    command = _get_command_from_graph(graph)
    process = Popen(args=command,
                    stdout=PIPE,
                    stderr=STDOUT,
                    shell=True)
    
    out, err = process.communicate()
    code = process.poll()

    if code:
        raise Error('ffmpeg', out, err)

    return out, err



@stream()
def graph(*args):
    """ Returns the chain of the nodes, printable for representations """
    return s.graph()
