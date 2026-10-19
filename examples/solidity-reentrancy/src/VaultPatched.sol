// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The developer's first attempt at fixing Vault.sol. Intentionally incomplete. Do not deploy.
contract VaultPatched {
    mapping(address => uint256) public balances;
    bool private locked;

    modifier nonReentrant() {
        require(!locked, "reentrant call");
        locked = true;
        _;
        locked = false;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient balance");
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] -= amount;
    }

    function withdrawAll() external nonReentrant {
        uint256 amount = balances[msg.sender];
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");
        balances[msg.sender] = 0;
    }
}
