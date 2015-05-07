
# See SprintInterface.py for another Sprint interface.
# This Sprint interface is to be used for ExternSprintDataset.

import os
from TaskSystem import Pickler, Unpickler

# Start Sprint PythonSegmentOrder interface. {
# We use the PythonSegmentOrder just to get an estimate (upper limit) about the number of sequences.

segmentOrderList = None; ":type: list[str] "

def getSegmentList(corpusName, segmentList, **kwargs):
  """
  Called by Sprint PythonSegmentOrder.
  Set python-segment-order = true in Sprint to use this.

  If this is used, this gets called really early.
  If it is used together with the Sprint PythonTrainer,
  it will get called way earlier before the init() below.
  It might also get called multiple times, e.g. if
  Sprint is in interactive mode to calc the seg count.
  This is optional. You can use the SprintInterface
  only for the PythonTrainer.

  :type corpusName: str
  :type segmentList: list[str]
  :rtype: list[str]
  :returns segment list. Can also be an iterator.
  """
  print("SprintExternInterface: getSegmentList(%r), num segments: %i" % (corpusName, len(segmentList)))
  global segmentOrderList
  segmentOrderList = segmentList
  # No shuffling here. We expect to do that via Sprint.
  return segmentList

# End Sprint PythonSegmentOrder interface. }

# Start Sprint PythonTrainer interface. {

isInitialized = False

def init(inputDim, outputDim, config, targetMode, **kwargs):
  """
  Called by Sprint when it initializes the PythonTrainer.
  Set trainer = python-trainer in Sprint to enable.
  Note that Sprint will call this, i.e. the trainer init lazily quite late,
  only once it sees the first data.

  :type inputDim: int
  :type outputDim: int
  :param str config: config string, passed by Sprint. assumed to be ","-separated
  :param str targetMode: "target-alignment" or "criterion-by-sprint" or so
  """
  print "PythonTrainer SprintExternInterface init()"
  print "inputDim:", inputDim
  print "outputDim:", outputDim
  print "config:", config
  print "targetMode:", targetMode
  print "other args:", kwargs

  global InputDim, OutputDim, isInitialized
  InputDim = inputDim
  OutputDim = outputDim
  isInitialized = True
  assert targetMode != "criterion-by-sprint"
  config = config.split(",")
  config = {key: value for (key, value) in [s.split(":", 1) for s in config if s]}
  assert config["action"] == "ExternSprintDataset"

  global sprintDataset
  numSegments = len(segmentOrderList) if segmentOrderList is not None else None
  sprintDataset = ExternSprintDatasetSource(c2p_fd=int(config["c2p_fd"]), p2c_fd=int(config["p2c_fd"]),
                                            inputDim=inputDim, outputDim=outputDim, numSegments=numSegments)

def exit():
  print "PythonTrainer SprintExternInterface exit()"
  assert isInitialized
  sprintDataset.close()

def feedInput(features, targetAlignment=None, weights=None, segmentName=None):
  assert features.shape[0] == InputDim
  sprintDataset.addNewData(features=features, targets=targetAlignment)

def feedInputAndTargetAlignment(features, targetAlignment, weights=None, segmentName=None):
  feedInput(features=features, targetAlignment=targetAlignment, weights=weights, segmentName=segmentName)

def feedInputAndTargetSegmentOrth(features, targetSegmentOrth, weights=None, segmentName=None):
  raise NotImplementedError

def feedInputUnsupervised(features, weights=None, segmentName=None):
  feedInput(segmentName=segmentName, features=features, weights=weights)

# End Sprint PythonTrainer interface. }


class ExternSprintDatasetSource:

  """
  This will send data to ExternSprintDataset over a pipe.
  We expect that we are child process and the parent process has spawned us via ExternSprintDataset
  and is waiting for our data.
  """

  def __init__(self, c2p_fd, p2c_fd, inputDim, outputDim, numSegments):
    """
    :param int c2p_fd: child-to-parent file descriptor
    :param int p2c_fd: parent-to-child file descriptor
    :type inputDim: int
    :type outputDim: int
    :type numSegments: int | None
    :param numSegments: can be None if not known in advance
    """
    self.pipe_c2p = os.fdopen(c2p_fd, "w")
    self.pipe_p2c = os.fdopen(p2c_fd, "r")
    self._send("init", (inputDim, outputDim, numSegments))

  def _send(self, dataType, args=None):
    Pickler(self.pipe_c2p).dump((dataType, args))
    self.pipe_c2p.flush()

  def addNewData(self, features, targets):
    self._send("data", (features, targets))

  def close(self):
    self._send("exit")
    self.pipe_c2p.close()
    self.pipe_p2c.close()
