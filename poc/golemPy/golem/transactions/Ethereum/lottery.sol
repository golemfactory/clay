contract LotteryAgent {

    uint golem_dep;  // golem account for provisions

   	struct LotteryData {
        uint value;			// lottery value
        uint timeout;		// maturity, then deadline
        uint deposit;		// winner deposit
        uint seed;			// maturity block hash
        address claimer;	// payer address, then winner address
    }

    mapping (bytes32 => LotteryData) lotteries;

	function initLottery(bytes32 descriptionHash, uint maturity, uint deposit) {
		LotteryData lottery = lotteries[descriptionHash];
		if (lottery.value != 0)
		    return;
		uint charge = msg.value / 20;
		golem_dep += charge;
		lotteries[descriptionHash] = LotteryData(msg.value-charge, maturity, deposit, 0, msg.sender);
	}

	function captureMaturityHash(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.seed != 0 || block.number <= lottery.timeout ||
	    block.number > lottery.timeout + 256) {
	        return;
	    }
	    address sendTo = lottery.claimer;
	    if (lottery.timeout + 128 < block.number)
	        sendTo = msg.sender;

       lottery.claimer = sendTo;
	   lottery.seed = random(lottery.timeout);
	   uint deposit = lottery.value/10;
	   lotteries[descriptionHash].value -= deposit;
	   sendTo.send(deposit);
    }

	function winnerLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || msg.value < lottery.deposit || block.number < lottery.timeout)
	        return;
	    if (lottery.seed != 0 && lottery.claimer != 0)
	        return;

	    if (lottery.seed == 0) {
	        replaceRandom(descriptionHash);
	    }
	    lottery.deposit = msg.value;
	    lottery.claimer = msg.sender;

	    lottery.timeout = now + 86400;
	}

	function payoutLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.seed == 0 || block.timestamp <= lottery.timeout)
	        return;
	    lottery.claimer.send(lottery.value);
	    delete lotteries[descriptionHash];
	}

	function checkLottery(uint maturity, uint lotteryId, uint startValue, address[] participants, uint[] probabilities) external {
	    bytes32 descriptionHash = sha3(maturity, lotteryId, startValue, participants, probabilities);
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || (lottery.seed == 0 && block.number <= lottery.timeout))
	        return;

	    if (lottery.seed == 0) {
	        replaceRandom(descriptionHash);
	    }

		address winner;
		uint target = 0;
		for (uint i = 0; i < probabilities.length; ++i) {
			target += probabilities[i];
			if (lottery.seed <= target) {
				winner = participants[i];
				break;
			}
		}

		uint value = lotteries[descriptionHash].value;
		if (lotteries[descriptionHash].claimer == 0) {
		    winner.send(value);
		} else {
		    if (winner != msg.sender) {
		        winner.send(value);
		        msg.sender.send(lotteries[descriptionHash].deposit);
		    } else {
		        winner.send(value + lotteries[descriptionHash].deposit);
		    }
		}
		delete lotteries[descriptionHash];

	}

	function random(uint maturity) internal constant returns(uint) {
	    while (block.number - maturity > 256) {
            maturity += 256;
	    }

		return uint(block.blockhash(maturity));
	}

    function replaceRandom(bytes32 descriptionHash) internal {
        LotteryData lottery = lotteries[descriptionHash];
	    lottery.seed = random(lottery.timeout);
	    uint deposit = lottery.value / 10;
	    lottery.value -= deposit;
	    if (block.number <= lottery.timeout + 128) {
	        lottery.claimer.send(deposit);
	    } else if (block.number > lottery.timeout + 256) {
	        golem_dep += deposit;
	    } else {
	        msg.sender.send(deposit);
	    }
	    lottery.claimer = 0;
	}

	function verifyLottery(bytes32 descriptionHash) returns (bool) {
	    return lotteries[descriptionHash].value == 0;
	}
}
