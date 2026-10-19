// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Intentionally vulnerable contract for the skills walkthrough. Do not deploy.
contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient balance");
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] -= amount;
    }

    function withdrawAll() external {
        uint256 amount = balances[msg.sender];
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] = 0;
    }
}
